# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import yaml

from collections import Mapping
from .exceptions import AnsibleContainerConfigException
from .utils import *

# TODO: Actually do some schema validation

class AnsibleContainerConfig(Mapping):
    _config = {}
    base_path = None

    def __init__(self, base_path):
        self.base_path = base_path
        self.config_path = os.path.join(self.base_path, 'ansible/container.yml')
        self.set_env('prod')

    def set_env(self, env):
        assert env in ['dev', 'prod']
        config = self._read_config()
        for service, service_config in config['services'].items():
            dev_overrides = service_config.pop('dev_overrides', {})
            if env == 'dev':
                service_config.update(dev_overrides)
        self._config = config

    def _read_config(self):
        try:
            ifs = open(self.config_path, 'r')
        except Exception:
            raise AnsibleContainerConfigException("Failed to open %s. Are you in the correct directory?" %
                                                  self.config_path)
        try:
            config = yaml.load(ifs)
        except Exception as exc:
            raise AnsibleContainerConfigException("Failed to parse container.yml - %s" % str(exc))
        ifs.close()
        return config

    def __getitem__(self, item):
        return self._config.get(item)

    def __iter__(self):
        return iter(self._config)

    def __len__(self):
        return len(self._config)

