# -*- coding: utf-8 -*-

from __future__ import absolute_import
from collections import OrderedDict


import logging

logger = logging.getLogger(__name__)


class Service(object):

    def __init__(self, config=None, project_name=None):
        self.project_name = project_name
        self.config = config

    def get_template(self):
        return self._get_task_or_config(request_type="config")

    def get_task(self):
        return self._get_task_or_config(request_type="task")

    def _get_task_or_config(self, request_type="task"):
        templates = []

        for name, service in self.config.get('services', {}).items():
            if service.get('ports'):
                if request_type == "task":
                    templates.append(self._create_task(name, service))
                elif request_type=="config":
                    templates.append(self._create_template(name, service))
        return templates

    def _create_template(self, name, service):
        '''
        Create a Kubernetes service template
        '''

        ports = self._get_ports(service)
        name = "%s-%s" % (self.project_name, name)
        labels = dict(
            app=self.project_name,
            service=name
        )

        template = dict(
            apiVersion="v1",
            kind="Service",
            metadata=dict(
                name=name,
                labels=labels.copy()
            ),
            spec=dict(
                selector=labels.copy(),
                ports=ports,
            )
        )

        template['spec']['type'] = 'NodeBalancer'
        for port in ports:
            if port['port'] != port['targetPort']:
                template['spec']['type'] = 'LoadBalancer'

        return template

    def _create_task(self, name, service):
        '''
        Generates an Ansible playbook task to deploy a service

        :param service:
        :return:
        '''

        ports = self._get_ports(service)
        name = "%s-%s" % (self.project_name, name)
        labels = dict(
            app=self.project_name,
            service=name
        )

        template = dict(
            kube_service=OrderedDict(
                service_name=name,
                ports=ports,
                selector=labels.copy()
            )
        )

        if service.get('labels'):
            template['kube_service']['labels'] = service.get('labels')

        load_balancer = False
        for port in ports:
            if port['port'] != port['targetPort']:
                load_balancer = True

        if load_balancer:
            template['kube_service']['type'] = 'LoadBalancer'

        return template

    @staticmethod
    def _get_ports(service):
        # TODO - handle port ranges
        ports = []
        for port in service['ports']:
            if isinstance(port, str) and ':' in port:
                parts = port.split(':')
                ports.append(dict(port=int(parts[0]), targetPort=int(parts[1]), name='port%s' % parts[0]))
            else:
                ports.append(dict(port=int(port), targetPort=int(port), name='port%s' % port))
        return ports