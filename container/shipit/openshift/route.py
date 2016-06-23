# -*- coding: utf-8 -*-

from __future__ import absolute_import
from collections import OrderedDict

import logging

logger = logging.getLogger(__name__)


class Route(object):

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
            if service.get('ports') and self._route_hostname(service):
                # If the service has a port and options.openshift.route_hostname,
                # then it gets a route, exposting it to the outside world.
                if request_type == "task":
                    templates.append(self._create_task(name, service))
                elif request_type == "config":
                    templates.append(self._create_template(name, service))
        return templates

    def _create_template(self, name, service):
        '''
        Generate an OpenShift route configuration
        '''

        service_port = self._get_exposed_port(service)
        hostname = self._route_hostname(service)
        name = "%s-route" % name
        labels = dict(
            app=self.project_name,
            service=name
        )

        template = dict(
            apiVersion="v1",
            kind="Route",
            metadata=dict(
                name=name,
                labels=labels.copy()
            ),
            spec=dict(
                host=hostname,
                to=dict(
                    kind='Service',
                    name="%s-%s" % (self.project_name, name),
                ),
                port=dict(
                    targetPort="port_%s" % service_port
                )
            )
        )
        return template

    def _create_task(self, name, service):
        '''
        Generates an Ansible playbook task.

        :param service:
        :return:
        '''
        service_port = self._get_exposed_port(service)
        hostname = self._route_hostname(service)
        name = "%s-route" % name
        labels = dict(
            app=self.project_name,
            service=name
        )
        template = dict(
            oso_route=OrderedDict(
                project_name=self.project_name,
                route_name=name,
                labels=labels.copy(),
                host=hostname,
                to="%s-%s" % (self.project_name, name),
                target_port="port_%s" % service_port
            )
        )
        return template

    def _get_exposed_port(self, service):
        '''
        Returns first port in the list of ports. If the port is a mapping,
        returns the first port of the mapping.

        :param service: dict of service attributes
        :return: port
        '''
        port = service['ports'][0]
        if isinstance(port, basestring):
            if ':' in port:
                parts = port.split(':')
                return parts[0]
        return port

    @staticmethod
    def _route_hostname(service):
        if 'options' in service:
            options = service['options']
            if 'openshift' in options:
                options = options['openshift']
                if 'route_hostname' in options:
                    return options['route_hostname']
        return False

