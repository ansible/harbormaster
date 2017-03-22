# -*- coding: utf-8 -*-
from __future__ import absolute_import

from container.common.visibility import getLogger
logger = getLogger(__name__)

import os
import json
import six

from collections import Mapping
from ruamel import yaml, ordereddict

from .common.exceptions import AnsibleContainerConfigException

# TODO: Actually do some schema validation

# jag: Division of labor between outer utility and conductor:
#
# Out here, we will parse the container.yml and process AC_* environment
# variables/--var-file into finding the resulting variable defaults values.
# We will do zero Jinja processing out here.
#
# Inside of the conductor, we will process metadata and defaults from roles and
# build service-level variables. And since Ansible is actually inside of the
# conductor container, it is _then_ that we will do Jinja2 processing of the
# given variable values

class AnsibleContainerConfig(Mapping):
    _config = ordereddict.ordereddict()
    base_path = None

    def __init__(self, base_path, var_file=None):
        self.base_path = base_path
        self.var_file = var_file
        self.config_path = os.path.join(self.base_path, 'container.yml')
        self.set_env('prod')

    def set_env(self, env):
        '''
        Loads config from container.yml,  and stores the resulting dict to self._config.

        :param env: string of either 'dev' or 'prod'. Indicates 'dev_overrides' handling.
        :return: None
        '''
        assert env in ['dev', 'prod']
        try:
            config = yaml.round_trip_load(open(self.config_path))
        except yaml.YAMLError as exc:
            raise AnsibleContainerConfigException(u"Parsing container.yml - %s" % unicode(exc))

        self._validate_config(config)

        for service, service_config in (config.get('services') or {}).items():
            if not service_config or isinstance(service_config, six.string_types):
                raise AnsibleContainerConfigException(u"Error: no definition found in container.yml for service %s."
                                                      % service)
            if isinstance(service_config, dict):
                dev_overrides = service_config.pop('dev_overrides', {})
                if env == 'dev':
                    service_config.update(dev_overrides)

        self._resolve_defaults(config)

        logger.debug(u"Parsed config", config=config)
        self._config = config

    def _resolve_defaults(self, config):
        """
        Defaults are in the container.yml, overridden by any --var-file param given,
        and finally overridden by any AC_* environment variables.

        :param config: Loaded YAML config
        :return: None
        """
        defaults = config.setdefault('defaults', ordereddict.ordereddict())
        if self.var_file:
            defaults.update(self._get_variables_from_file(), relax=True)
        logger.debug('The default type is', defaults=str(type(defaults)), config=str(type(config)))
        if type(defaults) == ordereddict.ordereddict:
            defaults.update(self._get_environment_variables(), relax=True)
        else:
            defaults.update(self._get_environment_variables())
        logger.debug(u'Resolved template variables', template_vars=defaults)

    def _get_environment_variables(self):
        '''
        Look for any environment variables that start with 'AC_'. Returns dict of key:value pairs, where the
        key is the result of removing 'AC_' from the variable name and converting the remainder to lowercase.
        For example, 'AC_DEBUG=1' becomes 'debug: 1'.

        :return ruamel.ordereddict.ordereddict
        '''
        logger.debug(u'Getting environment variables...')
        env_vars = ordereddict.ordereddict()
        for var, value in [(k, v) for k, v in six.iteritems(os.environ)
                           if k.startswith('AC_')]:
            env_vars[var[3:].lower()] = value
        logger.debug(u'Read environment variables', env_vars=env_vars)
        return env_vars

    def _get_variables_from_file(self):
        """
        Looks for file relative to base_path. If not found, checks relative to base_path/ansible.
        If file extension is .yml | .yaml, parses as YAML, otherwise parses as JSON.

        :return: ruamel.ordereddict.ordereddict
        """
        abspath = os.path.abspath(self.var_file)
        if not os.path.exists(abspath):
            dirname, filename = os.path.split(abspath)
            raise AnsibleContainerConfigException(
                u'Variables file "%s" not found. (I looked in "%s" for it.)' % (
                    filename, dirname))
        logger.debug("Use variable file: %s", abspath, file=abspath)

        if os.path.splitext(abspath)[-1].lower().endswith(('yml', 'yaml')):
            try:
                config = yaml.round_trip_load(open(abspath))
            except yaml.YAMLError as exc:
                raise AnsibleContainerConfigException(u"YAML exception: %s" % unicode(exc))
        else:
            try:
                config = json.loads(open(abspath))
            except Exception as exc:
                raise AnsibleContainerConfigException(u"JSON exception: %s" % unicode(exc))
        return config.iteritems()

    TOP_LEVEL_WHITELIST = [
        'version',
        'settings',
        'volumes',
        'services',
        'defaults',
        'registries'
    ]

    OPTIONS_KUBE_WHITELIST = []

    OPTIONS_OPENSHIFT_WHITELIST = []

    SUPPORTED_COMPOSE_VERSIONS = ['1', '2']

    def _validate_config(self, config):
        for top_level in config:
            if top_level not in self.TOP_LEVEL_WHITELIST:
                raise AnsibleContainerConfigException("invalid key '{0}'".format(top_level))
            if top_level == 'version':
                if config['version'] not in self.SUPPORTED_COMPOSE_VERSIONS:
                    raise AnsibleContainerConfigException("requested version is not supported")
                if config['version'] == '1':
                    logger.warning("Version '1' is deprecated. Consider upgrading to version '2'.")

    def __getitem__(self, item):
        return self._config.get(item)

    def __iter__(self):
        return iter(self._config)

    def __len__(self):
        return len(self._config)


