# -*- coding: utf-8 -*-
from __future__ import absolute_import

from container.utils.visibility import getLogger
logger = getLogger(__name__)

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from .base_deploy import K8sBaseDeploy

"""
Translate the container.yml derived config into an Ansible playbook/role
to deploy the services.
"""


class Deploy(K8sBaseDeploy):

    def get_namespace_task(self, state='present'):
        task = CommentedMap()
        task_name = 'Create namespace' if state == 'present' else 'Remove namespace'
        task['name'] = '{} {}'.format(task_name, self.namespace_name)
        task['k8s_v1_namespace'] = CommentedMap()
        task['k8s_v1_namespace']['name'] = self.namespace_name
        task['k8s_v1_namespace']['state'] = state
        return task

    def get_deployment_templates(self, default_api=None, defualt_kind=None, default_strategy=None):
        return super(Deploy, self).get_deployment_templates(default_api='extensions/v1beta1',
                                                            default_kind='deployment',
                                                            default_strategy='RollingUpdate')

    def get_deployment_tasks(self, module_name=None):
        return super(Deploy, self).get_deployment_tasks(module_name='k8s_v1beta1_deployment')
