# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import yaml

from collections import Mapping, OrderedDict
from .exceptions import AnsibleContainerConfigException
from .utils import *

# TODO: Actually do some schema validation


def represent_odict(dump, tag, mapping, flow_style=None):
    '''
    https://gist.github.com/miracle2k/3184458
    Like BaseRepresenter.represent_mapping, but does not issue the sort().
    '''
    value = []
    node = yaml.MappingNode(tag, value, flow_style=flow_style)
    if dump.alias_key is not None:
        dump.represented_objects[dump.alias_key] = node
    best_style = True
    if hasattr(mapping, 'items'):
        mapping = mapping.items()
    for item_key, item_value in mapping:
        node_key = dump.represent_data(item_key)
        node_value = dump.represent_data(item_value)
        if not (isinstance(node_key, yaml.ScalarNode) and not node_key.style):
            best_style = False
        if not (isinstance(node_value, yaml.ScalarNode) and not node_value.style):
            best_style = False
        value.append((node_key, node_value))
    if flow_style is None:
        if dump.default_flow_style is not None:
            node.flow_style = dump.default_flow_style
        else:
            node.flow_style = best_style
    return node


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

    def update_registries(self, registry_name=None, url=None, namespace=None):
        config = self._read_config()
        config_updated = False
        if registry_name and url:
            if not config.get('registries'):
                config['registries'] = {}
            if config['registries'].get(registry_name):
                if config['registries'][registry_name].get('url') != url:
                    config['registries'][registry_name]['url'] = url
                    config_updated = True
                if namespace and config['registries'][registry_name].get('namespace') != namespace:
                    config['registries'][registry_name]['namespace'] = namespace
                    config_updated = True
            else:
                config['registries'][registry_name] = {
                    u'url': url,
                    u'namespace': namespace
                }
                config_updated = True

        if config_updated:
            self._write_config(config)
        return config['registries'][registry_name].copy()

    def __getitem__(self, item):
        return self._config.get(item)

    def __iter__(self):
        return iter(self._config)

    def __len__(self):
        return len(self._config)

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

    def _write_config(self, config):
        # Write the config out in the same general order
        yaml.SafeDumper.add_representer(OrderedDict,
                                        lambda dumper, value: represent_odict(dumper, u'tag:yaml.org,2002:map', value))
        config_output = OrderedDict()
        config_output['version'] = config.get('version')
        config_output['services'] = config.get('services')
        if config.get('registries'):
            config_output['registries']=config.get('registries')
        try:
            ifs = open(self.config_path, 'w')
        except Exception:
            raise AnsibleContainerConfigException("Failed to update %s. Are you in the correct directory? "
                                                  "Do you have access?" % self.config_path)
        try:
            yaml.safe_dump(config_output, ifs, default_flow_style=False)
        except Exception as exc:
            raise AnsibleContainerConfigException("Failed to update container.yml - %s" % str(exc))
        ifs.close()


