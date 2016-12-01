#!/usr/bin/python
#
# Copyright 2016 Ansible by Red Hat
#
# This file is part of ansible-container
#

DOCUMENTATION = '''

module: oso_pvc

short_description: Create or remove a persistent volume claim.

description:
  - Create or remove a persistent volume claim on an OpenShift cluster by setting the C(state) to I(present) or I(absent).
  - The module is idempotent and will not replace an existing PVC unless the C(replace) option is passed.
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

logger = logging.getLogger('oso_pvc')

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
            'oso_pvc': {
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


class OSOPvcManager(object):

    def __init__(self):

        self.arg_spec = dict(
            project_name=dict(type='str', aliases=['namespace'], required=True),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
            name=dict(type='str', required=True),
            annotations=dict(type='dict',),
            access_modes=dict(type='list'),
            requested_storage=dict(type='str', default='1Gi'),
            match_labels=dict(type='dict',),
            match_expressions=dict(type='list',),
            volume_name=dict(type='str',),
            replace=dict(type='bool', default=False),
        )

        self.module = AnsibleModule(self.arg_spec,
                                    supports_check_mode=True)

        self.project_name = None
        self.state = None
        self.name = None
        self.annotations = None
        self.access_modes = None
        self.requested_storage = None
        self.match_labels = None
        self.match_expressions = None
        self.volume_name = None
        self.api = None
        self.replace = None
        self.check_mode = self.module.check_mode
        self.debug = self.module._debug

    def exec_module(self):

        for key in self.arg_spec:
            setattr(self, key, self.module.params.get(key))

        if self.debug:
            LOGGING['loggers']['container']['level'] = 'DEBUG'
            LOGGING['loggers']['oso_pvc']['level'] = 'DEBUG'
        logging.config.dictConfig(LOGGING)

        self.api = OriginAPI(self.module)

        actions = []
        changed = False
        claims = dict()
        results = dict()

        project_switch = self.api.set_project(self.project_name)
        if not project_switch:
            actions.append("Create project %s" % self.project_name)
            if not self.check_mode:
                self.api.create_project(self.project_name)

        if self.state == 'present':
            pvc = self.api.get_resource('pvc', self.name)
            if not pvc:
                template = self._create_template()
                changed = True
                actions.append("Create PVC %s" % self.name)
                if not self.check_mode:
                    self.api.create_from_template(template=template)
            elif pvc and self.replace:
                template = self._create_template()
                changed = True
                actions.append("Replace PVC %s" % self.name)
                if not self.check_mode:
                    self.api.replace_from_template(template=template)
            claims[self.name.replace('-', '_') + '_pvc'] = self.api.get_resource('pvc', self.name)
        elif self.state == 'absent':
            if self.api.get_resource('pvc', self.name):
                changed = True
                actions.append("Delete PVC %s" % self.name)
                if not self.check_mode:
                    self.api.delete_resource('pvc', self.name)

        results['changed'] = changed

        if self.check_mode:
            results['actions'] = actions

        if claims:
            results['ansible_facts'] = {u'volume_claims': claims}

        self.module.exit_json(**results)

    def _create_template(self):
        '''
        apiVersion: "v1"
        kind: "PersistentVolumeClaim"
        metadata:
          name: "claim1"
        spec:
          accessModes:
            - "ReadWriteOnce"
          resources:
            requests:
              storage: "5Gi"
          volumeName: "pv0001"
        '''

        template = dict(
            apiVersion="v1",
            kind="PersistentVolumeClaim",
            metadata=dict(
                name=self.name
            ),
            spec=dict()
        )

        if self.annotations:
            template['metadata']['annotations'] = self.annotations
        if self.access_modes:
            template['spec']['accessModes'] = self.access_modes
        if self.requested_storage:
            template['spec']['resources'] = {u'requests': {u'storage': self.requested_storage}}
        if self.match_labels:
            if not template['spec'].get('selector'):
                template['spec']['selector'] = {}
            template['spec']['selector']['match_labels'] = self.match_labels
        if self.match_expressions:
            if not template['spec'].get('selector'):
                template['spec']['selector'] = {}
            template['spec']['selector']['match_expressions'] = self.match_expressions
        if self.volume_name:
            template['spec']['volumeName'] = self.volume_name

        return template


#The following will be included by `ansble-container shipit` when cloud modules are copied into the role library path.
#include--> oso_api.py


def main():
    manager = OSOPvcManager()
    manager.exec_module()

if __name__ == '__main__':
    main()
