# -*- coding: utf-8 -*-
from __future__ import absolute_import

import copy
from six import iteritems

from ..config import BaseAnsibleContainerConfig
from ..utils.visibility import getLogger


logger = getLogger(__name__)


class AnsibleContainerConfig(BaseAnsibleContainerConfig):
    @property
    def image_namespace(self):
        return super(AnsibleContainerConfig, self).image_namespace

    def set_env(self, env):
        super(AnsibleContainerConfig, self).set_env(env)

        if self._config.get('volumes'):
            for vol_key in self._config['volumes']:
                if 'docker' in self._config['volumes'][vol_key]:
                    settings = copy.deepcopy(self._config['volumes'][vol_key][self.engine_name])
                    self._config['volumes'][vol_key] = settings
                else:
                    # remove non-docker settings
                    for engine_name in self.remove_engines:
                        if engine_name in self._config['volumes'][vol_key]:
                            del self._config['volumes'][vol_key][engine_name]

