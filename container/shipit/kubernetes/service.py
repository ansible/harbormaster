# -*- coding: utf-8 -*-

from __future__ import absolute_import
from collections import OrderedDict


import logging

logger = logging.getLogger(__name__)


class Service(object):

    def __init__(self, config=None, project_name=None):
        self.project_name = project_name
        self.config = config

    def get_template(self, service_names=None):
        return self._get_task_or_config(request_type="config", service_names=service_names)

    def get_task(self, service_names=None):
        return self._get_task_or_config(request_type="task", service_names=service_names)

    def _get_task_or_config(self, request_type="task", service_names=None):
        templates = []

        for name, service in self.config.get('services', {}).iteritems():
            if not service_names or name in service_names:
                if service.get('ports'):
                    if request_type == "task":
                        templates.append(self._create_task(service))
                    elif request_type=="config":
                        templates.append(self._create_template(service))
        return templates

    def _create_template(self, service):
        '''
        Crate a Kubernetes service template
        '''
        ports = self._get_ports(service)
        name = "%s-%s" % (self.project_name, service['name'])

        template = dict(
            apiVersion="v1",
            kind="Service",
            metadata=dict(
                name=name,
                labels=dict()
            ),
            spec=dict(
                selector=dict(),
                ports=ports,
            )
        )
        if service.get('labels'):
            template['metadata']['labels'] = service.get('labels')

        template['spec']['type'] = 'NodeBalancer'
        for port in ports:
            if port['port'] != port['targetPort']:
                template['spec']['type'] = 'LoadBalancer'

        template['spec']['selector'][service['name']] = service['name']

        return template

    def _create_task(self, service):
        '''
        Generates an Ansible playbook task to deploy a service

        :param service:
        :return:
        '''

        ports = self._get_ports(service)
        name = "%s-%s" % (self.project_name, service['name'])

        template = dict(
            k8s_service=OrderedDict(
                project_name=self.project_name,
                service_name=name,
                ports=ports,
                selector=dict()
            )
        )

        if service.get('labels'):
            template['k8s_service']['labels'] = service.get('labels')

        load_balancer = False
        for port in ports:
            if port['port'] != port['targetPort']:
                load_balancer = True

        if load_balancer:
            template['k8s_service']['type'] = LoadBalancer

        template['k8s_service']['selector'][service['name']] = service['name']

        return template

    @staticmethod
    def _get_ports(service):
        # TODO - handle port ranges
        ports = []
        for port in service['ports']:
            if isinstance(port, str) and ':' in port:
                parts = port.split(':')
                ports.append(dict(port=int(parts[0]), targetPort=int(parts[1]), name='port_%s' % parts[0]))
            else:
                ports.append(dict(port=int(port), targetPort=int(port)), name='port_%s' % port)
        return ports