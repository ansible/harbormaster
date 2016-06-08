
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
        resolved = []

        #
        # Grouping linked containers in the same pod is not working - that is communicating via 'localhost'
        # is not working.
        #
        # for service in self.config.services:
        #     # group linked services
        #     if not service_names or service['name'] in service_names:
        #         if service.get('links'):
        #             linked_containers = self._resolve_links(service.get('links'))
        #             logger.debug("linked containers: %s" % '.'.join(linked_containers))
        #             linked_containers.append(service['name'])
        #             logger.debug("linked containers: %s" % '.'.join(linked_containers))
        #             resolved += linked_containers
        #             if request_type == 'task':
        #                 new_template = self._create_task(linked_containers)
        #             elif request_type == 'config':
        #                 new_template = self._create_template(linked_containers)
        #             templates.append(new_template)

        for name, service in self.config.get('services', {}).iteritems():
            # add any non-linked services
            if not service_names or name in service_names:
                if name not in resolved:
                    if request_type == 'task':
                        new_template = self._create_task([service['name']])
                    elif request_type == 'config':
                        new_template = self._create_template([service['name']])
                    templates.append(new_template)

        return templates

    @staticmethod
    def _resolve_links(links):
        result = []
        for link in links:
            if ':' in link:
                target = link.split(':')[0]
            else:
                target = link
            # TODO - If the linked container has a port, ignore the link
            result.append(target)
        return result

    def _create_template(self, service_names):
        '''
        Creates a deployment template from a set of services. Each service is a container
        defined within the replication controller.
        '''

        name = "%s-%s" % (self.project_name, service_names[0])
        containers = self._services_to_containers(service_names, type="config")

        template = dict(
            apiVersion="v1",
            kind="DeploymentConfig",
            metadata=dict(
                name=name,
                labels=dict()
            ),
            spec=dict(
                template=dict(
                    metadata=dict(
                        labels=dict()
                    ),
                    spec=dict(
                        containers=containers
                    )
                ),
                replicas=1,
                selector=dict(),
                strategy=dict(
                    type='Rolling'
                )
            )
        )

        for service_name in service_names:
            template['metadata']['labels'][service_name] = 'yes'
            template['spec']['template']['metadata']['labels'][service_name] = 'yes'
            template['spec']['selector'][service_name] = 'yes'

        return template

    def _create_task(self, service_names):
        '''
        Generates an Ansible playbook task.

        :param service:
        :return:
        '''

        containers = self._services_to_containers(service_names, type="task")
        name = "%s-%s" % (self.project_name, service_names[0])

        template = dict(
            oso_deployment=OrderedDict(
                project_name=self.project_name,
                deployment_name=name,
                labels=dict(),
                containers=containers,
                selector=dict()
            )
        )

        for service_name in service_names:
            template['oso_deployment']['labels'][service_name] = service_name
            template['oso_deployment']['selector'][service_name] = service_name

        return template

    def _services_to_containers(self, service_names, type="task"):
        results = []
        for name, service in self.config.get('services', {}).iteritems():
            if name in service_names:
                container = OrderedDict(name=name)
                for key, value in service.items():
                    if key == 'ports' and type == 'config':
                        container['ports'] = self._get_config_ports(value)
                    elif key=='ports' and type == 'task':
                        container['ports'] = self._get_task_ports(value)
                    elif key in ('labels', 'links'):
                        pass
                    elif key == 'environment':
                        expanded_vars = self._expand_env_vars(value)
                        if type == 'config':
                            container['env'] = expanded_vars
                        else:
                            container['env'] = self._env_vars_to_task(expanded_vars)
                    else:
                        container[key] = value

                results.append(container)
        return results

    @staticmethod
    def _get_config_ports(ports):
        '''
        Convert docker ports to list of kube containerPort
        :param ports:
        :type ports: list
        :return: list
        '''
        results = []
        for port in ports:
            if ':' in port:
                parts = port.split(':')
                results.append(dict(containerPort=int(parts[1])))
            else:
                results.append(dict(containerPort=int(port)))
        return results

    @staticmethod
    def _get_task_ports(ports):
        '''
        Convert docker ports to list of ports to expose to the pod
        :param ports: list of compose style ports
        :type ports: list
        :return: list
        '''
        results = []
        for port in ports:
            if ':' in port:
                parts = port.split(':')
                results.append(int(parts[1]))
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
        Turn containier environment attribute into dictionary of name/value pairs.

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

    def _resolve_resource(self, path):
        result = path
        if '/' in path:
            # TODO - support other resource types?
            res_type, res_name = path.split('/')
            if res_type == 'service':
                parts = res_name.split(':')
                result = unicode("{{ %s_service.spec.clusterIP }}:%s" % (parts[0].replace('-', '_'), parts[1]))
        return result
