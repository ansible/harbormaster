# -*- coding: utf-8 -*-
from __future__ import absolute_import

from ..config import BaseAnsibleContainerConfig
from ..utils.visibility import getLogger


logger = getLogger(__name__)


class AnsibleContainerConfig(BaseAnsibleContainerConfig):
    @property
    def image_namespace(self):
        return self.project_name

    def set_env(self, env):
        super(AnsibleContainerConfig, self).set_env(env)