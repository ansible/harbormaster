#!/usr/bin/python
#
# Copyright 2016 Ansible by Red Hat
#
# This file is part of ansible-container
#

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

logger = logging.getLogger('oso_route')

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
            'oso_route': {
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


class RouteManager(object):

    def __init__(self):

        self.arg_spec = dict(
            project_name=dict(type='str', aliases=['namespace']),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
            labels=dict(type='dict'),
            route_name=dict(type='str'),
            host=dict(type='str'),
            service_name=dict(type='str', required=True, aliases=['to']),
            service_port=dict(type='str', required=True, aliases=['port']),
            replace=dict(type='bool', default=False),
            debug=dict(type='bool', default=False)
        )

        self.module = AnsibleModule(self.arg_spec,
                                    supports_check_mode=True)

        self.project_name = None
        self.state = None
        self.labels = None
        self.route_name = None
        self.host = None
        self.service_name = None
        self.service_port = None
        self.replace = None
        self.api = None
        self.debug = None
        self.check_mode = self.module.check_mode

    def exec_module(self):

        for key in self.arg_spec:
            setattr(self, key, self.module.params.get(key))

        if self.debug:
            LOGGING['loggers']['container']['level'] = 'DEBUG'
            LOGGING['loggers']['oso_route']['level'] = 'DEBUG'
        logging.config.dictConfig(LOGGING)

        self.api = OriginAPI(self.module)

        actions = []
        changed = False
        routes = dict()
        results = dict()

        project_switch = self.api.set_project(self.project_name)
        if not project_switch:
            actions.append("Create project %s" % self.project_name)
            if not self.check_mode:
                self.api.create_project(self.project_name)

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

        self.module.exit_json(**results)

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
                to=dict(
                    kind="Service",
                    name=self.service_name
                ),
                port=dict(
                    targetPort=self.service_port
                )
            )
        )

        if self.host:
            template['spec']['host'] = self.host

        if self.labels:
            template['metadata']['labels'] = self.labels

        return template

#The following will be included by `ansble-container shipit` when cloud modules are copied into the role library path.
#include--> oso_api.py


def main():
    manager = RouteManager()
    manager.exec_module()

if __name__ == '__main__':
    main()
