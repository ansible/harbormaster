# -*- coding: utf-8 -*-
from __future__ import absolute_import

import copy

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from .base_deploy import K8sBaseDeploy

from container.utils.visibility import getLogger
logger = getLogger(__name__)

"""
Translate the container.yml derived config into an Ansible playbook/role
to deploy the services.
"""


class Deploy(K8sBaseDeploy):

    def get_namespace_task(self, state='present', tags=[]):
        task = CommentedMap()
        task_name = 'Create namespace' if state == 'present' else 'Destroy the application by removing namespace'
        task['name'] = '{} {}'.format(task_name, self.namespace_name)
        task['k8s_v1_namespace'] = CommentedMap()
        task['k8s_v1_namespace']['name'] = self.namespace_name
        task['k8s_v1_namespace']['state'] = state
        if tags:
            task['tags'] = copy.copy(tags)
        return task

    def get_deployment_templates(self, default_api=None, defualt_kind=None, default_strategy=None, engine_state=None):
        strategy = {
            'type': 'RollingUpdate',
            'rolling_update': {
                'max_unavailable': '10%',
                'max_surge': '10%'
            }
        }
        return super(Deploy, self).get_deployment_templates(default_api='apps/v1beta1',
                                                            default_kind='deployment',
                                                            default_strategy=strategy,
                                                            engine_state=engine_state)

    def get_deployment_tasks(self, module_name=None, engine_state=None, tags=[]):
        return super(Deploy, self).get_deployment_tasks(module_name='k8s_apps_v1beta1_deployment',
                                                        engine_state=engine_state,
                                                        tags=tags)

