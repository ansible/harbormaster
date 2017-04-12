# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .utils.visibility import getLogger
logger = getLogger(__name__)

from io import BytesIO
import os
from os import path
import copy
import json
import six

from collections import Mapping
from ruamel import yaml

import container
if container.ENV == 'conductor':
    from ansible.template import Templar
from .exceptions import AnsibleContainerConfigException, AnsibleContainerNotInitializedException
from .utils import get_metadata_from_role, get_defaults_from_role

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
    _config = yaml.compat.ordereddict()
    base_path = None

    @container.host_only
    def __init__(self, base_path, var_file=None, engine_name=None):
        self.base_path = base_path
        self.var_file = var_file
        self.engine_name = engine_name
        self.config_path = path.join(self.base_path, 'container.yml')
        self.set_env('prod')

    @property
    def deployment_path(self):
        return (self['settings'] or {}).get(
            'deployment_output_path',
            path.normpath(
                path.abspath(
                    path.expanduser(
                        path.join(self.base_path, 'ansible-deployment/')
                    )
                )
            )
        )

    def set_env(self, env):
        """
        Loads config from container.yml,  and stores the resulting dict to self._config.

        :param env: string of either 'dev' or 'prod'. Indicates 'dev_overrides' handling.
        :return: None
        """
        assert env in ['dev', 'prod']
        try:
            config = yaml.round_trip_load(open(self.config_path))
        except IOError:
            raise AnsibleContainerNotInitializedException()
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
            if self.engine_name not in ('openshift', 'k8s'):
                if 'k8s' in service_config:
                    del service_config['k8s']
                if 'openshift' in service_config:
                    del service_config['openshift']

        if config.get('volumes'):
            # Adjust volumes based on engine_name
            if self.engine_name == 'docker':
                # For docker replace all attributes with just those for docker
                for vol_key in list(config['volumes'].keys()):
                    if 'docker' in config['volumes'][vol_key]:
                        docker_settings = copy.deepcopy(config['volumes'][vol_key])
                        config['volumes'][vol_key] = docker_settings
            elif self.engine_name in ('openshift', 'k8s'):
                # For openshift/k8s remove unrelated attributes
                for vol_key in config['volumes'].keys():
                    for engine_key in list(config['volumes'][vol_key].keys()):
                        if engine_key != self.engine_name:
                            del config['volumes'][vol_key][engine_key]

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
        defaults = config.setdefault('defaults', yaml.compat.ordereddict())
        if self.var_file:
            defaults.update(self._get_variables_from_file(), relax=True)
        logger.debug('The default type is', defaults=str(type(defaults)), config=str(type(config)))
        if six.PY2 and type(defaults) == yaml.compat.ordereddict:
            defaults.update(self._get_environment_variables(), relax=True)
        else:
            defaults.update(self._get_environment_variables())
        logger.debug(u'Resolved template variables', template_vars=defaults)

    @staticmethod
    def _get_environment_variables():
        '''
        Look for any environment variables that start with 'AC_'. Returns dict of key:value pairs, where the
        key is the result of removing 'AC_' from the variable name and converting the remainder to lowercase.
        For example, 'AC_DEBUG=1' becomes 'debug: 1'.

        :return ruamel.yaml.compat.ordereddict
        '''
        logger.debug(u'Getting environment variables...')
        env_vars = yaml.compat.ordereddict()
        for var, value in ((k, v) for k, v in os.environ.items()
                           if k.startswith('AC_')):
            env_vars[var[3:].lower()] = value
        logger.debug(u'Read environment variables', env_vars=env_vars)
        return env_vars

    def _get_variables_from_file(self):
        """
        Looks for file relative to base_path. If not found, checks relative to base_path/ansible.
        If file extension is .yml | .yaml, parses as YAML, otherwise parses as JSON.

        :return: ruamel.yaml.compat.ordereddict
        """
        abspath = path.abspath(self.var_file)
        if not path.exists(abspath):
            dirname, filename = path.split(abspath)
            raise AnsibleContainerConfigException(
                u'Variables file "%s" not found. (I looked in "%s" for it.)' % (
                    filename, dirname))
        logger.debug("Use variable file: %s", abspath, file=abspath)

        if path.splitext(abspath)[-1].lower().endswith(('yml', 'yaml')):
            try:
                config = yaml.round_trip_load(open(abspath))
            except yaml.YAMLError as exc:
                raise AnsibleContainerConfigException(u"YAML exception: %s" % unicode(exc))
        else:
            try:
                config = json.loads(open(abspath))
            except Exception as exc:
                raise AnsibleContainerConfigException(u"JSON exception: %s" % unicode(exc))
        return six.iteritems(config)

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
            else:
                if config[top_level] is None:
                    config[top_level] = yaml.compat.ordereddict()

    def __getitem__(self, item):
        return self._config[item]

    def __iter__(self):
        return iter(self._config)

    def __len__(self):
        return len(self._config)


class AnsibleContainerConductorConfig(Mapping):
    _config = None

    @container.conductor_only
    def __init__(self, container_config):
        self._config = container_config
        self._templar = Templar(loader=None, variables={})
        self._process_defaults()
        self._process_top_level_sections()
        self._process_services()

    def _process_section(self, section_value, callback=None, templar=None):
        if not templar:
            templar = self._templar
        processed = yaml.compat.ordereddict()
        for key, value in section_value.items():
            if isinstance(value, basestring):
                # strings can be templated
                processed[key] = templar.template(value)
            elif isinstance(value, (list, dict)):
                # if it's a dimensional structure, it's cheaper just to serialize
                # it, treat it like a template, and then deserialize it again
                buffer = BytesIO() # use bytes explicitly, not unicode
                yaml.round_trip_dump(value, buffer)
                processed[key] = yaml.round_trip_load(
                    templar.template(buffer.getvalue())
                )
            else:
                # ints, booleans, etc.
                processed[key] = value
            if callback:
                callback(processed)
        return processed

    def _process_defaults(self):
        logger.debug('Processing defaults section...')
        self.defaults = self._process_section(
            self._config.get('defaults', yaml.compat.ordereddict()),
            callback=lambda processed: self._templar.set_available_variables(
                dict(processed)))

    def _process_top_level_sections(self):
        for section in ['volumes', 'registries']:
            logger.debug('Processing section...', section=section)
            setattr(self, section,
                    self._process_section(self._config.get(
                        section, yaml.compat.ordereddict())))

    def _process_services(self):
        services = yaml.compat.ordereddict()
        for service, service_data in self._config.get(
                'services', yaml.compat.ordereddict()).items():
            logger.debug('Processing service...', service=service)
            processed = yaml.compat.ordereddict()
            service_defaults = self.defaults.copy()
            for role_spec in service_data.get('roles', []):
                if isinstance(role_spec, dict):
                    # A role with parameters to run it with
                    role_spec_copy = role_spec.copy()
                    role_name = role_spec_copy.pop('role')
                    role_args = role_spec_copy
                else:
                    role_name = role_spec
                    role_args = {}
                role_metadata = get_metadata_from_role(role_name)
                processed.update(role_metadata, relax=True)
                service_defaults.update(get_defaults_from_role(role_name),
                                        relax=True)
                service_defaults.update(role_args, relax=True)
            processed.update(service_data, relax=True)
            logger.debug('Rendering service keys from defaults',
                service=service, defaults=service_defaults)
            services[service] = self._process_section(
                processed,
                templar=Templar(loader=None, variables=service_defaults)
            )
        self.services = services

    def __getitem__(self, key):
        if key.startswith('_'):
            raise KeyError(key)
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __len__(self):
        # volumes, registries, services, and defaults
        return 4

    def __iter__(self):
        yield self.defaults
        yield self.registries
        yield self.volumes
        yield self.services
