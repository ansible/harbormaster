#!/usr/bin/python
#
# Copyright 2016 Ansible by Red Hat
#
# This file is part of ansible-container
#

DOCUMENTATION = '''

module: oso_service

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

logger = logging.getLogger('oso_service')

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
            'oso_service': {
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


class OSOServiceManager(object):

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
            debug=dict(type='bool', default=False)
        )

        self.module = AnsibleModule(self.arg_spec,
                                    supports_check_mode=True)

        self.project_name = None
        self.state = None
        self.labels = None
        self.ports = None
        self.service_name = None
        self.loadbalancer = None
        self.selector = None
        self.replace = None
        self.api = None
        self.debug = None
        self.check_mode = self.module.check_mode

    def exec_module(self):

        for key in self.arg_spec:
            setattr(self, key, self.module.params.get(key))

        if self.debug:
            LOGGING['loggers']['container']['level'] = 'DEBUG'
            LOGGING['loggers']['oso_service']['level'] = 'DEBUG'
        logging.config.dictConfig(LOGGING)

        self.api = OriginAPI(self.module)

        actions = []
        changed = False
        services = dict()
        results = dict()

        project_switch = self.api.set_project(self.project_name)
        if not project_switch:
            actions.append("Create project %s" % self.project_name)
            if not self.check_mode:
                self.api.create_project(self.project_name)

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

        self.module.exit_json(**results)

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


#The following will be included by `ansble-container shipit` when cloud modules are copied into the role library path.
#include--> oso_api.py


def main():
    manager = OSOServiceManager()
    manager.exec_module()

if __name__ == '__main__':
    main()
