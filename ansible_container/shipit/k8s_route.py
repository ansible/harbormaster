# -*- coding: utf-8 -*-

from __future__ import absolute_import
from collections import OrderedDict


import logging

logger = logging.getLogger(__name__)


class K8SRoute(object):

    def __init__(self, config=None, project_name=None):
        self.project_name = project_name
        self.config = config

    def get_template(self, service_names=None):
        return self._get_task_or_config(request_type="config", service_names=service_names)

    def get_task(self, service_names=None):
        return self._get_task_or_config(request_type="task", service_names=service_names)

    def _get_task_or_config(self, request_type="task", service_names=None):
        templates = []
        for service in self.config.services:
            if not service_names or service['name'] in service_names:
                if service.get('labels'):
                    for key, value in service['labels'].items():
                        if key == 'k8s_expose_as':
                            if request_type == "task":
                                templates.append(self._create_task(service))
                            elif request_type=="config":
                                templates.append(self._create_template(service))

        return templates

    def _create_template(self, service):
        '''
        apiVersion: v1
        kind: Route
        metadata:
          name: wordpress-wordpress
          labels:
            wordpress: wordpress
        spec:
          host: wordpress.local
          to:
            kind: Service
            name: wordpress-wordpress
          port:
            targetPort: main
        '''

        host = self._get_host(service)
        labels = self._get_labels(service)
        name = "%s-route" % service['name']

        template = dict(
            apiVersion="v1",
            kind="Route",
            metadata=dict(
                name=name,
                labels=labels
            ),
            spec=dict(
                host=host,
                to=dict(
                    kind='Service',
                    name="%s-%s" % (self.project_name, service['name']),
                ),
                port=dict(
                    targetPort="port0"
                )
            )
        )

        return template

    def _create_task(self, service):
        '''
        Generates an Ansible playbook task.

        :param service:
        :return:
        '''

        host = self._get_host(service)
        labels = self._get_labels(service)
        name = "%s-route" % service['name']

        template = dict(
            k8s_route=OrderedDict(
                project_name=self.project_name,
                route_name=name,
                labels=labels,
                host=host,
                to="%s-%s" % (self.project_name, service['name']),
                target_port="port0"
            )
        )

        return template

    @staticmethod
    def _get_host(service):
        host = None
        for key, value in service['labels'].items():
            if key == 'k8s_expose_as':
                host = value
        return host

    @staticmethod
    def _get_labels(service):
        result = dict()
        result[service['name']] = service['name']
        if service.get('labels'):
            labels = service['labels']
            for key, value in labels.items():
                if 'k8s_' not in key:
                    result[key] = value

        for key, value in result.items():
            if not isinstance(value, str):
                result[key] = str(value)
        return result