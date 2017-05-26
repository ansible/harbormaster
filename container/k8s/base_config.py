# -*- coding: utf-8 -*-
from __future__ import absolute_import

from ..config import BaseAnsibleContainerConfig
from ..utils.visibility import getLogger


logger = getLogger(__name__)


class K8sBaseConfig(BaseAnsibleContainerConfig):

    @property
    def image_namespace(self):
        namespace = self.project_name
        if self._config.get('settings', {}).get('k8s_namespace', {}).get('name'):
            namespace = self._config['settings']['k8s_namespace']['name']
        return namespace

    def set_env(self, env):
        super(K8sBaseConfig, self).set_env(env)

        if self._config.get('volumes'):
            for vol_key in self._config['volumes']:
                # Remove settings not meant for this engine
                for engine_name in self.remove_engines:
                    if engine_name in self._config['volumes'][vol_key]:
                        del self._config['volumes'][vol_key][engine_name]
