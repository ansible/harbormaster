# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import yaml
import re

from collections import Mapping
from .exceptions import AnsibleContainerRegistryFileException


class AnsibleContainerRegistry(Mapping):
    _config = {}
    base_path = None
    comments = ''

    def __init__(self, base_path):
        self.base_path = base_path
        self.config_path = os.path.join(self.base_path, 'ansible/registry.yml')
        self._config = self._get_config()

    def update(self, registry_name=None, url=None, namespace=None):
        self._config = self._get_config()
        config_updated = False
        if registry_name and url:
            if self._config.get(registry_name):
                if self._config[registry_name].get('url') != url:
                    self._config[registry_name]['url'] = url
                    config_updated = True
                if namespace and self._config[registry_name].get('namespace') != namespace:
                    self._config[registry_name]['namespace'] = namespace
                    config_updated = True
            else:
                self._config[registry_name] = {
                    u'url': url,
                    u'namespace': namespace
                }
                config_updated = True
        if config_updated:
            self._write_config()
        return self._config[registry_name].copy()

    def _get_config(self):
        try:
            ifs = open(self.config_path, 'r')
        except Exception:
            raise AnsibleContainerRegistryFileException("Failed to open %s. Are you in the correct directory?" %
                                               self.config_path)
        try:
            data = ''
            self.comments = ''
            for line in ifs:
                if re.match(r'^#', line):
                    self.comments += line
                else:
                    data += line
            config = yaml.load(data)
        except Exception as exc:
            raise AnsibleContainerRegistryFileException("Failed to parse registry.yml - %s" % str(exc))
        ifs.close()
        return config.get('registries')

    def _write_config(self):
        data = dict(
            registries=self._config
        )
        try:
            ifs = open(self.config_path, 'w')
        except Exception:
            raise AnsibleContainerRegistryFileException("Failed to update %s. Are you in the correct directory? "
                                                        "Do you have write access?" % self.config_path)
        try:
           ifs.write(self.comments)
           ifs.write(u'---\n')
           ifs.write(yaml.safe_dump(data, default_flow_style=False))
        except Exception as exc:
            raise AnsibleContainerRegistryFileException("Failed to update registry.yml - %s" % str(exc))
        ifs.close()

    def __getitem__(self, item):
        return self._config.get(item)

    def __iter__(self):
        return iter(self._config)

    def __len__(self):
        return len(self._config)


