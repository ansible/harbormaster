# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
from collections import OrderedDict

from ..base_engine import BaseShipItObject

logger = logging.getLogger(__name__)


class Service(BaseShipItObject):

    def _get_template_or_task(self, request_type="task"):
        templates = []
        for name, service in self.config.get('services', {}).items():
            new_service = self._create(name, request_type, service)
            if new_service:
                templates.append(new_service)
            if service.get('links'):
                templates += self._create_alias_templates(request_type, service['links'])
        return templates

    def _create_alias_templates(self, request_type, links):
        '''
        If a service defines aliased links, create a service template for each alias.

        :param request_type: will be 'config' or 'task'
        :param links: list of links
        :return: list of templates
        '''
        templates = []
        for link in links:
            if ':' not in link:
                continue
            service_name, alias = link.split(':')
            alias_config = self.config['services'].get(service_name)
            if alias_config:
                new_service = self._create(alias, request_type, alias_config)
                if new_service:
                    templates.append(new_service)
        return templates

    def _create(self, name, request_type, service):
        '''
        Create a Kubernetes service template or playbook task
        :param request_type:
        '''

        template = {}
        ports = self._get_ports(service)
        options = service.get('options', {}).get('kube', {})
        state = options.get('state', 'present')

        if ports:
            labels = dict(
                app=self.project_name,
                service=name
            )
            if request_type == 'config' and state != 'absent':
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

                for port in ports:
                    if port['port'] != port['targetPort']:
                        template['spec']['type'] = 'LoadBalancer'
            elif request_type == 'task':
                template = dict(
                    kube_service=OrderedDict(
                        service_name=name,
                        ports=ports,
                        selector=labels.copy()
                    )
                )

                if service.get('labels'):
                    template['kube_service']['labels'] = service.get('labels')

                for port in ports:
                    if port['port'] != port['targetPort']:
                        template['kube_service']['type'] = 'LoadBalancer'

        return template

    def _get_ports(self, service):
        # TODO - handle port ranges
        ports = []
        for port in service.get('ports', []):
            if isinstance(port, str) and ':' in port:
                parts = port.split(':')
                if not self._port_in_list(parts[0], ports):
                    ports.append(dict(port=int(parts[0]), targetPort=int(parts[1]), name='port-%s' % parts[0]))
            else:
                if not self._port_in_list(port, ports):
                    ports.append(dict(port=int(port), targetPort=int(port), name='port-%s' % port))

        for port in service.get('expose', []):
            if not self._port_in_list(port, ports):
                ports.append(dict(port=int(port), targetPort=int(port), name='port-%s' % port))
        return ports

    @staticmethod
    def _port_in_list(port, ports):
        found = False
        for p in ports:
            if p['port'] == int(port):
                found = True
                break
        return found
