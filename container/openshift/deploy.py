# -*- coding: utf-8 -*-
from __future__ import absolute_import

import copy

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from six import string_types

from ..k8s.base_deploy import K8sBaseDeploy

from container.utils.visibility import getLogger

logger = getLogger(__name__)

"""
Translate the container.yml derived config into an Ansible playbook/role
to deploy the services.
"""


class Deploy(K8sBaseDeploy):

    CONFIG_KEY = 'openshift'

    def get_namespace_task(self, state='present', tags=[]):
        task = CommentedMap()
        module_name = 'openshift_v1_project'
        task_name = 'Create project' if state == 'present' else 'Destroy the application by removing project'
        task['name'] = '{} {}'.format(task_name, self._namespace_name)
        task[module_name] = CommentedMap()
        task[module_name]['name'] = self._namespace_name
        if state == 'present':
            if self._namespace_display_name:
                task[module_name]['display_name'] = self._namespace_display_name
            if self._namespace_description:
                task[module_name]['description'] = self._namespace_description
        task[module_name]['state'] = state
        if tags:
            task['tags'] = copy.copy(tags)
        return task

    def get_deployment_templates(self, default_api=None, defualt_kind=None, default_strategy=None, engine_state=None):
        strategy = {
            'type': 'Rolling',
        }
        return super(Deploy, self).get_deployment_templates(default_api='v1',
                                                            default_kind='deployment_config',
                                                            default_strategy=strategy,
                                                            engine_state=engine_state)

    def get_deployment_tasks(self, module_name=None, engine_state=None, tags=[]):
        return super(Deploy, self).get_deployment_tasks(module_name='openshift_v1_deployment_config',
                                                        engine_state=engine_state,
                                                        tags=tags)

    def get_route_templates(self):
        """
        Generate Openshift route templates or playbook tasks. Each port on a service definition found in container.yml
        represents an externally exposed port.
        """
        def _get_published_ports(service_config):
            result = []
            for port in service_config.get('ports', []):
                protocol = 'TCP'
                if isinstance(port, string_types) and '/' in port:
                    port, protocol = port.split('/')
                if isinstance(port, string_types) and ':' in port:
                    host, container = port.split(':')
                else:
                    host = port
                result.append({'port': host, 'protocol': protocol.lower()})
            return result

        templates = []
        for name, service_config in self._services.items():
            state = service_config.get(self.CONFIG_KEY, {}).get('state', 'present')
            force = service_config.get(self.CONFIG_KEY, {}).get('force', False)
            published_ports = _get_published_ports(service_config)

            if state != 'present':
                continue

            for port in published_ports:
                route_name = "%s-%s" % (name, port['port'])
                labels = dict(
                    app=self._namespace_name,
                    service=name
                )
                template = CommentedMap()
                template['apiVersion'] = self.DEFAULT_API_VERSION
                template['kind'] = 'Route'
                template['force'] = force
                template['metadata'] = CommentedMap([
                    ('name', route_name),
                    ('namespace', self._namespace_name),
                    ('labels', labels.copy())
                ])
                template['spec'] = CommentedMap([
                    ('to', CommentedMap([
                        ('kind', 'Service'),
                        ('name', name)
                    ])),
                    ('port', CommentedMap([
                        ('targetPort', 'port-{}-{}'.format(port['port'], port['protocol']))
                    ]))
                ])

                if service_config.get(self.CONFIG_KEY, {}).get('routes'):
                    for route in service_config[self.CONFIG_KEY]['routes']:
                        if str(route.get('port')) == str(port['port']):
                            for key, value in route.items():
                                if key not in ('force', 'port'):
                                    self.copy_attribute(template['spec'], key, value)

                templates.append(template)

        return templates

    def get_route_tasks(self, tags=[]):
        module_name = 'openshift_v1_route'
        tasks = []
        for template in self.get_route_templates():
            task = CommentedMap()
            task['name'] = 'Create route'
            task[module_name] = CommentedMap()
            task[module_name]['state'] = 'present'
            if self._auth:
                for key in self._auth:
                    task[module_name][key] = self._auth[key]
            task[module_name]['force'] = template.pop('force', False)
            task[module_name]['resource_definition'] = template
            if tags:
                task['tags'] = copy.copy(tags)
            tasks.append(task)
        for name, service_config in self._services.items():
            # Remove routes where state is 'absent'
            if service_config.get(self.CONFIG_KEY, {}).get('state', 'present') == 'absent':
                task = CommentedMap()
                task['name'] = 'Remove route'
                task[module_name] = CommentedMap()
                task[module_name]['state'] = 'absent'
                if self._auth:
                    for key in self._auth:
                        task[module_name][key] = self._auth[key]
                task[module_name]['name'] = name
                task[module_name]['namespace'] = self._namespace_name
                if tags:
                    task['tags'] = copy.copy(tags)
                tasks.append(task)
        return tasks
