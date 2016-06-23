
# -*- coding: utf-8 -*-

from __future__ import absolute_import


import logging
import re
from collections import OrderedDict

logger = logging.getLogger(__name__)


class Deployment(object):

    def __init__(self, config=None, project_name=None):
        self.project_name = project_name
        self.config = config

    def get_template(self, service_names=None):
        return self._get_template_or_task(request_type="config", service_names=service_names)

    def get_task(self, service_names=None):
        return self._get_template_or_task(request_type="task", service_names=service_names)

    def _get_template_or_task(self, request_type="task", service_names=None):
        templates = []
        for name, service in self.config.get('services', {}).items():
            if request_type == 'task':
                new_template = self._create_task(name, service)
            elif request_type == 'config':
                new_template = self._create_template(name, service)
            templates.append(new_template)
        return templates

    def _create_template(self, name, service):
        '''
        Creates a deployment template from a service.
        '''

        name = "%s-%s" % (self.project_name, name)
        container = self._service_to_container(name, service, type="config")
        labels = dict(
            app=self.project_name,
            service=name
        )

        template = dict(
            apiVersion="v1",
            kind="DeploymentConfig",
            metadata=dict(
                name=name,
                labels=labels.copy()
            ),
            spec=dict(
                template=dict(
                    metadata=dict(
                        labels=labels.copy()
                    ),
                    spec=dict(
                        containers=container
                    )
                ),
                replicas=1,
                selector=dict(),
                strategy=dict(
                    type='Rolling'
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
        name = "%s-%s" % (self.project_name, name)
        container = self._service_to_container(name, service, type="task")
        labels = dict(
            app=self.project_name,
            service=name
        )
        template = dict(
            oso_deployment=OrderedDict(
                project_name=self.project_name,
                deployment_name=name,
                labels=labels.copy(),
                container=container,
                selector=labels.copy()
            )
        )
        return template

    def _service_to_container(self, name, service, type="task"):
        container = OrderedDict(name=name)
        for key, value in service.items():
            if key == 'ports':
                container['ports'] = self._get_ports(value, type)
            elif key in ('labels', 'links', 'options', 'dev_options'):
                pass
            elif key == 'environment':
                expanded_vars = self._expand_env_vars(value)
                if type == 'config':
                    container['env'] = expanded_vars
                else:
                    container['env'] = self._env_vars_to_task(expanded_vars)
            else:
                container[key] = value
        return container

    @staticmethod
    def _get_ports(ports, type):
        '''
        Determine the list of ports to expose from the container.

        :param: list of port mappings
        :return: list
        '''
        results = []
        for port in ports:
            if ':' in port:
                parts = port.split(':')
                if type == 'config':
                    results.append(dict(containerPort=int(parts[1])))
                else:
                    results.append(int(parts[1]))
            else:
                if type == 'config':
                    results.append(dict(containerPort=int(port)))
                else:
                    results.append(int(port))
        return results

    @staticmethod
    def _env_vars_to_task(env_vars):
        '''
        Turn list of vars into a dict for playbook task.
        :param env_variables: list of dicts
        :return: dict
        '''
        result = dict()
        for var in env_vars:
            result[var['name']] = var['value']
        return result

    def _expand_env_vars(self, env_variables):
        '''
        Turn container environment attribute into dictionary of name/value pairs.

        :param env_variables: container env attribute value
        :type env_variables: dict or list
        :return: dict
        '''
        def r(x, y):
            if re.match('shipit_', x, flags=re.I):
                return dict(name=re.sub('^shipit_', '', x, flags=re.I), value=self._resolve_resource(y))
            return dict(name=x, value=y)

        results = []
        if isinstance(env_variables, dict):
            for key, value in env_variables.items():
                results.append(r(key, value))
        elif isinstance(env_variables, list):
            for envvar in env_variables:
                parts = envvar.split('=')
                if len(parts) == 1:
                    results.append(dict(name=re.sub('^shipit_', '', parts[0], flags=re.I), value=None))
                elif len(parts) == 2:
                    results.append(r(parts[0], parts[1]))
        return results
