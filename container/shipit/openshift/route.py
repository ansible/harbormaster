# -*- coding: utf-8 -*-

from __future__ import absolute_import
import logging

logger = logging.getLogger(__name__)


import re

from collections import OrderedDict
from six import string_types


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
            new_routes = self._create(request_type, name, service)
            if new_routes:
                templates += new_routes
        return templates

    def _create(self, type, name, service):
        '''
        Generate Openshift route templates or playbook tasks. Each port on a service definition
        represents an externally exposed port.
        '''

        templates = []
        hostname = None

        options = service.get('options', {}).get('openshift', {})
        state = options.get('state', 'present')

        if options.get('hostname'):
            hostname = options['hostname']

        service_ports = self._get_service_ports(service)

        if service_ports:
            for port in service_ports:
                route_name = "%s-%s" % (name, port)
                labels = dict(
                    app=self.project_name,
                    service=name
                )

                if type == 'config' and state != 'absent':
                    template = dict(
                        apiVersion="v1",
                        kind="Route",
                        metadata=dict(
                            name=route_name,
                            labels=labels.copy()
                        ),
                        spec=dict(
                            to=dict(
                                kind='Service',
                                name=name,
                            ),
                            port=dict(
                                targetPort="port-%s" % port
                            )
                        )
                    )
                    if hostname:
                        template['spec']['host'] = hostname
                else:
                    template = dict(
                        oso_route=OrderedDict(
                            project_name=self.project_name,
                            route_name=route_name,
                            labels=labels.copy(),
                            service_name=name,
                            service_port="port-%s" % port,
                            replace=True,
                        )
                    )
                    if hostname:
                        template['oso_route']['host'] = hostname

                    template['oso_route']['state'] = state

                templates.append(template)

        return templates

    def _get_service_ports(self, service):
        '''
        Get the external port and the target container port.

        :param service: dict of service attributes
        :return: (external port, target port)
        '''

        #TODO: port ranges?

        result = []
        for port in service.get('ports', []):
            if isinstance(port, string_types) and ':' in port:
                parts = port.split(':')
                result.append(parts[0])
            else:
                result.append(port)
        return result
