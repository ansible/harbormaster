# -*- coding: utf-8 -*-
from __future__ import absolute_import

from ..utils.visibility import getLogger

from ..k8s.base_config import K8sBaseConfig


logger = getLogger(__name__)


class AnsibleContainerConfig(K8sBaseConfig):

    @property
    def image_namespace(self):
        return super(AnsibleContainerConfig, self).image_namespace

    def set_env(self, env):
        super(AnsibleContainerConfig, self).set_env(env)
