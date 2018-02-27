# -*- coding: utf-8 -*-
from __future__ import absolute_import

from six import iteritems

from ..utils.visibility import getLogger

from .base_config import K8sBaseConfig


logger = getLogger(__name__)


class AnsibleContainerConfig(K8sBaseConfig):

    @property
    def image_namespace(self):
        return super(AnsibleContainerConfig, self).image_namespace

    def set_env(self, env):
        super(AnsibleContainerConfig, self).set_env(env)

        for name, service in iteritems(self._config['services']):
            if 'containers' in service:
                for c in service['containers']:
                    self._update_service_config(env, c)
