#!/usr/bin/python
#
# Copyright 2016 Red Hat | Ansible
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.


DOCUMENTATION = '''

module: k8s_deployment

short_description: Start, cancel or retry a deployment on a Kubernetes or OpenShift cluster.

description:
  - Start, cancel or retry a deployment on a Kubernetes or OpenShift cluster by setting the C(state) to I(present) or
    I(absent).
  - Supports check mode. Use check mode to view a list of actions the module will take.

options:

'''

EXAMPLES = '''
'''

RETURN = '''
'''
import logging
import logging.config

from ansible.module_utils.basic import *
from ansible_container.shipit.k8s_api import K8sApi
from ansible_container.shipit.exceptions import ShipItException

logger = logging.getLogger('k8s_deployment')

LOGGING = (
    {
        'version': 1,
        'disable_existing_loggers': True,
        'handlers': {
            'null': {
                'level': 'DEBUG',
                'class': 'logging.NullHandler',
            },
            'file': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filename': 'ansible-container.log'
            }
        },
        'loggers': {
            'k8s_deployment': {
                'handlers': ['file'],
                'level': 'INFO',
            },
            'container': {
                'handlers': ['file'],
                'level': 'INFO',
            },
            'compose': {
                'handlers': [],
                'level': 'INFO'
            },
            'docker': {
                'handlers': [],
                'level': 'INFO'
            }
        },
    }
)

class K8SDeploymentManager(AnsibleModule):

    def __init__(self):

        self.arg_spec = dict(
            project_name=dict(type='str', aliases=['namespace'], required=True),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
            labels=dict(type='dict'),
            deployment_name=dict(type='str'),
            recreate=dict(type='bool', default=False),
            replace=dict(type='bool', default=True),
            selector=dict(type='dict'),
            replicas=dict(type='int', default=1),
            containers=dict(type='list'),
            strategy=dict(type='str', default='Rolling', choices=['Recreate', 'Rolling']),
            cli=dict(type='str', choices=['kubectl', 'oc'], default='oc'),
            debug=dict(type='bool', default=False)
        )

        super(K8SDeploymentManager, self).__init__(self.arg_spec,
                                                   supports_check_mode=True)

        self.project_name = None
        self.state = None
        self.labels = None
        self.ports = None
        self.deployment_name = None
        self.selector = None
        self.replace = None
        self.replicas = None
        self.containers = None
        self.strategy = None
        self.recreate = None
        self.cli = None
        self.api = None
        self.debug = None

    def exec_module(self):

        for key in self.arg_spec:
            setattr(self, key, self.params.get(key))

        if self.debug:
            LOGGING['loggers']['container']['level'] = 'DEBUG'
            LOGGING['loggers']['k8s_deployment']['level'] = 'DEBUG'
        logging.config.dictConfig(LOGGING)

        self.api = K8sApi(target=self.cli)

        actions = []
        changed = False
        deployments = dict()
        results = dict()

        try:
            project_switch = self.api.set_project(self.project_name)
        except ShipItException as exc:
            self.fail_json(msg=exc.message, stderr=exc.stderr, stdout=exc.stdout)
        if not project_switch:
            actions.append("Create project %s" % self.project_name)
            if not self.check_mode:
                try:
                    self.api.create_project(self.project_name)
                except ShipItException as exc:
                    self.fail_json(msg=exc.message, stderr=exc.stderr, stdout=exc.stdout)

        if self.state == 'present':
            deployment = self.api.get_resource('dc', self.deployment_name)
            if not deployment:
                template = self._create_template()
                changed = True
                actions.append("Create deployment %s" % self.deployment_name)
                if not self.check_mode:
                    try:
                        self.api.create_from_template(template=template)
                    except ShipItException as exc:
                        self.fail_json(msg=exc.message, stderr=exc.stderr, stdout=exc.stdout)
            elif deployment and self.recreate:
                actions.append("Delete deployment %s" % self.deployment_name)
                changed = True
                template = self._create_template()
                if not self.check_mode:
                    try:
                        self.api.delete_resource('dc', self.deployment_name)
                        self.api.create_from_template(template=template)
                    except ShipItException as exc:
                        self.fail_json(msg=exc.message, stderr=exc.stderr, stdout=exc.stdout)
            elif deployment and self.replace:
                template = self._create_template()
                try:
                    template['status'] = dict(latestVersion=deployment['status']['latestVersion'] + 1)
                except Exception as exc:
                    self.fail_json(msg="Failed to increment latestVersion for %s - %s" % (self.deployment_name,
                                                                                          str(exc)))
                changed = True
                actions.append("Update deployment %s" % self.deployment_name)
                if not self.check_mode:
                    try:
                        self.api.replace_from_template(template=template)
                    except ShipItException as exc:
                        self.fail_json(msg=exc.message, stderr=exc.stderr, stdout=exc.stdout)

            deployments[self.deployment_name.replace('-', '_') + '_deployment'] = self.api.get_resource('dc', self.deployment_name)
        elif self.state == 'absent':
            if self.api.get_resource('deployment', self.deployment_name):
                changed = True
                actions.append("Delete deployment %s" % self.deployment_name)
                if self.check_mode:
                    try:
                        self.api.delete_resource('deployment', self.deployment_name)
                    except ShipItException as exc:
                        self.fail_json(msg=exc.message, stderr=exc.stderr, stdout=exc.stdout)
        results['changed'] = changed
        if self.check_mode:
            results['actions'] = actions
        if deployments:
            results['ansible_facts'] = deployments
        return results

    def _create_template(self):

        for container in self.containers:
            if container.get('env'):
                container['env'] = self._env_to_list(container['env'])
            if container.get('ports'):
                container['ports'] = self._port_to_container_ports(container['ports'])

        template = dict(
            apiVersion="v1",
            kind="DeploymentConfig",
            metadata=dict(
                name=self.deployment_name,
            ),
            spec=dict(
                template=dict(
                    metadata=dict(),
                    spec=dict(
                        containers=self.containers
                    )
                ),
                replicas=self.replicas,
                strategy=dict(
                    type=self.strategy,
                ),
            )
        )

        if self.labels:
            template['metadata']['labels'] = self.labels
            template['spec']['template']['metadata']['labels'] = self.labels

        if self.selector:
            template['spec']['selector'] = self.selector

        return template

    def _env_to_list(self, env_variables):
        result = []
        for name, value in env_variables.items():
            result.append(dict(
                name=name,
                value=value
            ))
        return result

    @staticmethod
    def _port_to_container_ports(ports):
        result = []
        for port in ports:
            result.append(dict(containerPort=port))
        return result

def main():
    manager = K8SDeploymentManager()
    results = manager.exec_module()
    manager.exit_json(**results)


if __name__ == '__main__':
    main()
