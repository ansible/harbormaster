# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import yaml

from collections import Mapping
from .exceptions import AnsibleContainerRegistryFileException
from .utils import *

# TODO: Actually do some schema validation


class AnsibleContainerRegistry(Mapping):
    _config = {}
    base_path = None

    def __init__(self, base_path):
        self.base_path = base_path
        self.config_path = os.path.join(self.base_path, 'ansible/registry.yml')
        self._config = self._get_config()

    def update(self, registry_name=None, url=None, namespace=None):
        self._config = self._get_config()
        config_updated = False
        if registry_name and url:
            if self._config['registries'].get(registry_name):
                if self._config['registries'][registry_name].get('url') != url:
                    self._config['registries'][registry_name]['url'] = url
                    config_updated = True
                if namespace and self._config['registries'][registry_name].get('namespace') != namespace:
                    self._config['registries'][registry_name]['namespace'] = namespace
                    config_updated = True
            else:
                self._config['registries'][registry_name] = {
                    u'url': url,
                    u'namespace': namespace
                }
                config_updated = True
        if config_updated:
            self._write_config()
        return self._config['registries'][registry_name].copy()

    def __getitem__(self, item):
        return self._config.get(item)

    def __iter__(self):
        return iter(self._config)

    def __len__(self):
        return len(self._config)

    def _get_config(self):
        try:
            ifs = open(self.config_path, 'r')
        except Exception:
            raise AnsibleContainerRegistryFileException("Failed to open %s. Are you in the correct directory?" %
                                               self.config_path)
        try:
            config = yaml.load(ifs)
        except Exception as exc:
            raise AnsibleContainerRegistryFileException("Failed to parse registry.yml - %s" % str(exc))
        ifs.close()
        return config

    def _write_config(self, config):
        try:
            ifs = open(self.config_path, 'w')
        except Exception:
            raise AnsibleContainerRegistryFileException("Failed to update %s. Are you in the correct directory? "
                                                        "Do you have write access?" % self.config_path)
        try:
            yaml.safe_dump(self._config, ifs, default_flow_style=False)
        except Exception as exc:
            raise AnsibleContainerRegistryFileException("Failed to update registry.yml - %s" % str(exc))
        ifs.close()


