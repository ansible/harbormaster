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

module: k8s_route

short_description: Create or remove a route on a Kubernetes or OpenShift cluster.

description:
  - Create or remove a route on a Kubernetes or OpenShift cluster by setting the C(state) to I(present) or I(absent).
  - The module is idempotent and will not replace an existing route unless the C(reload) option is passed.
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

logger = logging.getLogger('k8s_route')

LOGGING = (
    {
        'version': 1,
        'disable_existing_loggers': True,
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
            },
            'file': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filename': 'ansible-container.log'
            }
        },
        'loggers': {
            'k8s_route': {
                'handlers': ['file'],
                'level': 'DEBUG',
            },
            'container': {
                'handlers': ['file'],
                'level': 'DEBUG',
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


class K8SRouteManager(AnsibleModule):

    def __init__(self):

        self.arg_spec = dict(
            project_name=dict(type='str', aliases=['namespace']),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
            labels=dict(type='dict'),
            route_name=dict(type='str'),
            host=dict(type='str', required=True),
            to_service=dict(type='str', required=True, aliases=['to']),
            target_port=dict(type='str', required=True, aliases=['port']),
            replace=dict(type='bool', default=False),
            cli=dict(type='str', choices=['kubectl', 'oc'], default='oc'),
            debug=dict(type='bool', default=False)
        )

        super(K8SRouteManager, self).__init__(self.arg_spec,
                                              supports_check_mode=True)

        self.project_name = None
        self.state = None
        self.labels = None
        self.route_name = None
        self.host = None
        self.to_service = None
        self.target_port = None
        self.replace = None
        self.cli = None
        self.api = None
        self.debug = None

    def exec_module(self):

        for key in self.arg_spec:
            setattr(self, key, self.params.get(key))

        if self.debug:
            LOGGING['loggers']['container']['level'] = 'DEBUG'
            LOGGING['loggers']['k8s_route']['level'] = 'DEBUG'
        logging.config.dictConfig(LOGGING)

        self.api = K8sApi(target=self.cli)

        actions = []
        changed = False
        routes = dict()
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
            route = self.api.get_resource('route', self.route_name)
            if not route:
                template = self._create_template()
                changed = True
                actions.append("Create route %s" % self.route_name)
                if not self.check_mode:
                    self.api.create_from_template(template=template)
            elif route and self.replace:
                template = self._create_template()
                changed = True
                actions.append("Replace route %s" % self.route_name)
                if not self.check_mode:
                    self.api.replace_from_template(template=template)
            routes[self.route_name.replace('-', '_') + '_route'] = self.api.get_resource('route', self.route_name)
        elif self.state == 'absent':
            if self.api.get_resource('route', self.route_name):
                changed = True
                actions.append("Delete route %s" % self.route_name)
                if not self.check_mode:
                    self.api.delete_resource('route', self.route_name)

        results['changed'] = changed
        if self.check_mode:
            results['actions'] = actions
        if routes:
            results['ansible_facts'] = routes
        return results

    def _create_template(self):
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

        template = dict(
            apiVersion="v1",
            kind="Route",
            metadata=dict(
                name=self.route_name,
            ),
            spec=dict(
                host=self.host,
                to=dict(
                    kind="Service",
                    name=self.to_service
                ),
                port=dict(
                    targetPort=self.target_port
                )
            )
        )

        if self.labels:
            template['metadata']['labels'] = self.labels

        return template


def main():
    manager = K8SRouteManager()
    results = manager.exec_module()
    manager.exit_json(**results)


if __name__ == '__main__':
    main()
