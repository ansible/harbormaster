#!/usr/bin/python
#
# Copyright 2016 Ansible by Red Hat
#
# This file is part of ansible-container
#

DOCUMENTATION = '''

module: oso_deployment

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

logger = logging.getLogger('oso_deployment')

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
            'oso_deployment': {
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


class DeploymentManager(object):

    def __init__(self):

        self.arg_spec = dict(
            project_name=dict(type='str', aliases=['namespace'], required=True),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
            labels=dict(type='dict'),
            deployment_name=dict(type='str', aliases=['name']),
            recreate=dict(type='bool', default=False),
            replace=dict(type='bool', default=True),
            replicas=dict(type='int', default=1),
            containers=dict(type='list'),
            strategy=dict(type='str', default='Rolling', choices=['Recreate', 'Rolling']),
            volumes=dict(type='list'),
        )

        self.module = AnsibleModule(self.arg_spec,
                                    supports_check_mode=True)

        self.project_name = None
        self.state = None
        self.labels = None
        self.deployment_name = None
        self.replace = None
        self.replicas = None
        self.containers = None
        self.strategy = None
        self.recreate = None
        self.volumes = None
        self.api = None
        self.check_mode = self.module.check_mode
        self.debug = self.module._debug

    def exec_module(self):

        for key in self.arg_spec:
            setattr(self, key, self.module.params.get(key))

        if self.debug:
            LOGGING['loggers']['container']['level'] = 'DEBUG'
            LOGGING['loggers']['oso_deployment']['level'] = 'DEBUG'
        logging.config.dictConfig(LOGGING)

        self.api = OriginAPI(self.module)

        actions = []
        changed = False
        deployments = dict()
        results = dict()

        project_switch = self.api.set_project(self.project_name)
        if not project_switch:
            actions.append("Create project %s" % self.project_name)
            if not self.check_mode:
                self.api.create_project(self.project_name)

        if self.state == 'present':
            deployment = self.api.get_resource('dc', self.deployment_name)
            if not deployment:
                template = self._create_template()
                changed = True
                actions.append("Create deployment %s" % self.deployment_name)
                if not self.check_mode:
                    self.api.create_from_template(template=template)
            elif deployment and self.recreate:
                actions.append("Delete deployment %s" % self.deployment_name)
                changed = True
                template = self._create_template()
                if not self.check_mode:
                    self.api.delete_resource('dc', self.deployment_name)
                    self.api.create_from_template(template=template)
            elif deployment and self.replace:
                template = self._create_template()
                template['status'] = dict(latestVersion=deployment['status']['latestVersion'] + 1)
                changed = True
                actions.append("Update deployment %s" % self.deployment_name)
                if not self.check_mode:
                    self.api.replace_from_template(template=template)

            deployments[self.deployment_name.replace('-', '_') + '_deployment'] = self.api.get_resource('dc', self.deployment_name)

        elif self.state == 'absent':
            if self.api.get_resource('dc', self.deployment_name):
                changed = True
                actions.append("Delete deployment %s" % self.deployment_name)
                if not self.check_mode:
                    self.api.delete_resource('dc', self.deployment_name)

        results['changed'] = changed
        if self.check_mode:
            results['actions'] = actions

        if deployments:
            results['ansible_facts'] = deployments

        self.module.exit_json(**results)

    def _create_template(self):

        for container in self.containers:
            if container.get('env'):
                container['env'] = self._env_to_list(container['env'])

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

        if self.volumes:
            template['spec']['template']['spec']['volumes'] = self.volumes

        if self.labels:
            template['metadata']['labels'] = self.labels
            template['spec']['template']['metadata']['labels'] = self.labels

        return template

    @staticmethod
    def _env_to_list(env_variables):
        result = []
        for name, value in env_variables.items():
            result.append(dict(
                name=name,
                value=value
            ))
        return result


#The following will be included by `ansble-container shipit` when cloud modules are copied into the role library path.
#include--> oso_api.py


def main():
    manager = DeploymentManager()
    manager.exec_module()

if __name__ == '__main__':
    main()
