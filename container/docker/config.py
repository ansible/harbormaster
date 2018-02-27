# -*- coding: utf-8 -*-
from __future__ import absolute_import

import copy

from ruamel import yaml
from six import iteritems

from ..config import BaseAnsibleContainerConfig
from ..exceptions import AnsibleContainerConfigException, AnsibleContainerNotInitializedException
from ..utils.visibility import getLogger


logger = getLogger(__name__)


class AnsibleContainerConfig(BaseAnsibleContainerConfig):
    @property
    def image_namespace(self):
        return self.project_name

    def set_env(self, env, config=None):
        try:
            config = yaml.round_trip_load(open(self.config_path))
        except IOError:
            raise AnsibleContainerNotInitializedException()
        except yaml.YAMLError as exc:
            raise AnsibleContainerConfigException(u"Parsing container.yml - %s" % exc)

        new_services = yaml.compat.ordereddict()
        for service_name, service_config in iteritems(config.get('services') or {}):
            if service_config.get('containers'):
                # If containers is defined, convert it to services, and drop any other keys
                for container in service_config['containers']:
                    if not container.get('container_name'):
                        raise AnsibleContainerConfigException(
                            u"Expecting container to have container_name defined. None found."
                        )
                    new_service_name = "{}-{}".format(service_name, container['container_name'])
                    new_services[new_service_name] = copy.deepcopy(container)
            else:
                new_services[service_name] = copy.deepcopy(service_config)

        config['services'] = new_services
        super(AnsibleContainerConfig, self).set_env(env, config=config)

        if self._config.get('volumes'):
            for vol_key in self._config['volumes']:
                if 'docker' in self._config['volumes'][vol_key]:
                    settings = copy.deepcopy(self._config['volumes'][vol_key][self.engine_name])
                    self._config['volumes'][vol_key] = settings
                else:
                    # remove non-engine settings
                    for engine_name in self.remove_engines:
                        if engine_name in self._config['volumes'][vol_key]:
                            del self._config['volumes'][vol_key][engine_name]
