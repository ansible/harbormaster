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
        apiVersion: v1
            kind: Service
            metadata:
              name: frontend
              labels:
                app: guestbook
                tier: frontend
            spec:
              # if your cluster supports it, uncomment the following to automatically create
              # an external load-balanced IP for the frontend service.
              # type: LoadBalancer
              ports:
                # the port that this service should serve on
              - port: 80
              selector:
                app: guestbook
                tier: frontend
        '''

        labels = self._get_labels(service)
        ports = self._get_ports(service)
        name = "%s-%s" % (self.project_name, service['name'])

        template = dict(
            apiVersion="v1",
            kind="Service",
            metadata=dict(
                name=name,
                labels=labels
            ),
            spec=dict(
                selector=dict(),
                ports=ports,
            )
        )

        template['spec']['selector'][service['name']] = 'yes'

        if self._get_load_balancer(service):
            template['spec']['type'] = 'LoadBalancer'

        return template

    def _create_task(self, service):
        '''
        Generates an Ansible playbook task.

        :param service:
        :return:
        '''

        labels = self._get_labels(service)
        ports = self._get_ports(service)
        name = "%s-%s" % (self.project_name, service['name'])

        template = dict(
            oso_service=OrderedDict(
                project_name=self.project_name,
                service_name=name,
                labels=labels,
                ports=ports,
                selector=dict()
            )
        )

        if self._get_load_balancer(service):
            template['oso_service']['loadbalancer'] = True

        template['oso_service']['selector'][service['name']] = service['name']

        return template

    @staticmethod
    def _get_load_balancer(service):
        result = None
        if service.get('labels'):
            labels = service['labels']
            if labels.get('oso_service_type') == 'loadbalancer':
                result = labels['oso_service_type']
        return result

    @staticmethod
    def _get_labels(service):
        result = dict()
        result[service['name']] = service['name']
        if service.get('labels'):
            labels = service['labels']
            for key, value in labels.items():
                if 'oso_' not in key:
                    result[key] = value

        for key, value in result.items():
            if not isinstance(value, str):
                result[key] = str(value)
        return result

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