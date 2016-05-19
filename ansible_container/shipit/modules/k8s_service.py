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

module: k8s_service

short_description: Create or remove a service on a Kubernetes or OpenShift cluster.

description:
  - Create or remove a service on a Kubernetes or OpenShift cluster by setting the C(state) to I(present) or I(absent).
  - The module is idempotent and will not replace an existing service unless the C(reload) option is passed.
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

logger = logging.getLogger('k8s_service')

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
            'k8s_service': {
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


class K8SServiceManager(AnsibleModule):

    def __init__(self):

        self.arg_spec = dict(
            project_name=dict(type='str', aliases=['namespace'], required=True),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
            labels=dict(type='dict'),
            ports=dict(type='list', required=True),
            service_name=dict(type='str', required=True),
            loadbalancer=dict(type='bool', default=False),
            replace=dict(type='bool', default=False),
            selector=dict(type='dict', required=True),
            cli=dict(type='str', choices=['kubectl', 'oc'], default='oc'),
            debug=dict(type='bool', default=False)
        )

        super(K8SServiceManager, self).__init__(self.arg_spec,
                                                supports_check_mode=True)

        self.project_name = None
        self.state = None
        self.labels = None
        self.ports = None
        self.service_name = None
        self.loadbalancer = None
        self.selector = None
        self.replace = None
        self.cli = None
        self.api = None
        self.debug = None

    def exec_module(self):

        for key in self.arg_spec:
            setattr(self, key, self.params.get(key))

        if self.debug:
            LOGGING['loggers']['container']['level'] = 'DEBUG'
            LOGGING['loggers']['k8s_service']['level'] = 'DEBUG'
        logging.config.dictConfig(LOGGING)

        self.api = K8sApi(target=self.cli)

        actions = []
        changed = False
        services = dict()
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
            service = self.api.get_resource('service', self.service_name)
            if not service:
                template = self._create_template()
                changed = True
                actions.append("Create service %s" % self.service_name)
                if not self.check_mode:
                    self.api.create_from_template(template=template)
            elif service and self.replace:
                template = self._create_template()
                changed = True
                actions.append("Replace service %s" % self.service_name)
                if not self.check_mode:
                    self.api.replace_from_template(template=template)
            services[self.service_name.replace('-', '_') + '_service'] = self.api.get_resource('service', self.service_name)
        elif self.state == 'absent':
            if self.api.get_resource('service', self.service_name):
                changed = True
                actions.append("Delete service %s" % self.service_name)
                if not self.check_mode:
                    self.api.delete_resource('service', self.service_name)

        results['changed'] = changed
        if self.check_mode:
            results['actions'] = actions
        if services:
            results['ansible_facts'] = services
        return results

    def _create_template(self):
        '''
        apiVersion: v1
            kind: Service
            metadata:
              name: frontend
              labels:
                app: guestbook
                tier: frontend
            spec:
              # if your cluster supports it, uncomment the following to automatically create
              # an external load-balanced IP for the frontend service.
              # type: LoadBalancer
              ports:
                # the port that this service should serve on
              - port: 80
              selector:
                app: guestbook
                tier: frontend
        '''

        selector = self.selector if self.selector else self.service_name
        self._update_ports()

        template = dict(
            apiVersion="v1",
            kind="Service",
            metadata=dict(
                name=self.service_name
            ),
            spec=dict(
                selector=selector,
                ports=self.ports
            )
        )

        if self.labels:
            template['metadata']['labels'] = self.labels

        if self.loadbalancer:
            template['spec']['type'] = 'LoadBalancer'

        return template

    def _update_ports(self):
        count = 0
        for port in self.ports:
            if not port.get('name'):
                port['name'] = "port%s" % count
                count += 1
            if not port.get('type'):
                port['type'] = "TCP"

def main():
    manager = K8SServiceManager()
    results = manager.exec_module()
    manager.exit_json(**results)


if __name__ == '__main__':
    main()
