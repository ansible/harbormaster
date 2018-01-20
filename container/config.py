# -*- coding: utf-8 -*-
from __future__ import absolute_import


from .utils.visibility import getLogger
logger = getLogger(__name__)

from abc import ABCMeta, abstractproperty, abstractmethod
from io import BytesIO
import os
from os import path
import copy
import json
import re
from six import add_metaclass, iteritems, PY2, string_types, text_type

from collections import Mapping
from .utils.ordereddict import ordereddict
from .utils import resolve_config_path
from ruamel import yaml
import jsonschema
import container

if container.ENV == 'conductor':
    from ansible.template import Templar
    try:
        from ansible.utils.unsafe_proxy import AnsibleUnsafeText
    except ImportError:
        from ansible.vars.unsafe_proxy import AnsibleUnsafeText

from .exceptions import (AnsibleContainerConfigException, AnsibleContainerNotInitializedException,
                         AnsibleContainerRequestException)
from .utils import get_metadata_from_role, get_defaults_from_role

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


DEFAULT_CONDUCTOR_BASE = 'centos:7'


@add_metaclass(ABCMeta)
class BaseAnsibleContainerConfig(Mapping):
    _config = ordereddict()
    base_path = None
    engine_list = ['docker', 'openshift', 'k8s']

    @container.host_only
    def __init__(self, base_path, vars_files=None, engine_name=None, project_name=None, vault_files=None,
                 config_file=None):
        self.base_path = base_path
        self.cli_vars_files = vars_files
        self.engine_name = engine_name
        self.config_path = resolve_config_path(base_path, config_file)
        self.cli_project_name = project_name
        self.cli_vault_files = vault_files
        self.remove_engines = set(self.engine_list) - set([engine_name])
        self.set_env('prod')

    @property
    def deployment_path(self):
        dep_path = self.get('settings', ordereddict()).get('deployment_output_path',
                            path.join(self.base_path, 'ansible-deployment/'))
        return path.normpath(path.abspath(path.expanduser(path.expandvars(dep_path))))

    @property
    def project_name(self):
        if self.cli_project_name:
            # Give precedence to CLI args
            self._validate_project_name(self.cli_project_name)
            return self.cli_project_name
        if self._config.get('settings', {}).get('project_name', None):
            # Look for settings.project_name
            self._validate_project_name(self._config['settings']['project_name'])
            return self._config['settings']['project_name']
        logger.info("Setting project_name not defined. Fallback to current directory name.")
        self._validate_project_name(os.path.basename(self.base_path))
        return os.path.basename(self.base_path)

    @property
    def conductor_base(self):
        if self._config.get('settings', {}).get('conductor_base'):
            return self._config['settings']['conductor_base']
        if self._config.get('settings', {}).get('conductor', {}).get('base'):
            return self._config['settings']['conductor']['base']
        return DEFAULT_CONDUCTOR_BASE

    @property
    def vault_files(self):
        if self.cli_vault_files:
            # Give precedence to CLI args
            return self.cli_vault_files
        if self._config.get('settings', {}).get('vault_files'):
            return self._config['settings']['vault_files']

    @property
    def vault_password_file(self):
        if self.cli_vault_password_file:
            # Give precedence to CLI args
            return self.cli_vault_password_file
        if self._config.get('settings', {}).get('vault_password_file'):
            return self._config['settings']['vault_password_file']

    @property
    def save_conductor(self):
        return self._config.get('settings', {}).get('save_conductor_container', False) or \
               self._config.get('settings', {}).get('conductor', {}).get('save', False)

    @property
    @abstractproperty
    def image_namespace(self):
        # When pushing images or deploying, we need to know the default namespace
        pass

    def get_conductor_environment(self):
        """
        Return a copy of settings.conductor.environment + any undefined environment variables found in 
        any service definitions. Sets any undefined variables to corresponding variables found in the 
        local environment. 
        """  
        conductor_env = copy.deepcopy(self._config.get('settings', {}).get('conductor', {}).get('environment', {}))
        if isinstance(conductor_env, list):
            # convert to a dict 
            new_env = {}
            for item in [e.split('=', 1) for e in conductor_env if '=' in e]:
                new_env[item[0]] = item[1]
            for item in [e for e in conductor_env if '=' not in e]:
                new_env[item] = None
            conductor_env = new_env
         
        for name, options in iteritems(self._config['services']):
            if options.get('environment'):
                if isinstance(options['environment'], list):
                    for e in options['environment']:
                        if '=' not in e and os.environ.get(e) and not conductor_env.get(e):
                            conductor_env[e] = os.environ[e]
                elif isinstance(options['environment'], dict):
                    for key, value in iteritems(options['environment']):
                        if value is None and os.environ.get(key) and not conductor_env.get(key):
                            conductor_env[key] = os.environ[key]    

        for key in conductor_env.keys():
            if conductor_env[key] is None:
                conductor_env[key] = os.environ.get(key)

        return conductor_env 

    def set_conductor_environment(self, environment):
        if self._config.get('settings') is None: 
            self._config['settings'] = {}
        if self._config['settings'].get('conductor') is None:
            self._config['settings']['conductor'] = {}
        self._config['settings']['conductor']['environment'] = environment

    @abstractmethod
    def set_env(self, env, config=None):
        """
        Loads config from container.yml,  and stores the resulting dict to self._config.

        :param env: string of either 'dev' or 'prod'. Indicates 'dev_overrides' handling.
        :return: None
        """
        assert env in ['dev', 'prod']

        if not config:
            try:
                config = yaml.round_trip_load(open(self.config_path))
            except IOError:
                raise AnsibleContainerNotInitializedException()
            except yaml.YAMLError as exc:
                raise AnsibleContainerConfigException(u"Parsing container.yml - %s" % text_type(exc))

        self._validate_config(config)

        for service, service_config in iteritems(config.get('services') or {}):
            if not service_config or isinstance(service_config, string_types):
                raise AnsibleContainerConfigException(u"Error: no definition found in container.yml for service %s."
                                                      % service)
            self._update_service_config(env, service_config)

        # Insure settings['pwd'] = base_path. Will be used later by conductor to resolve $PWD in volumes.
        if config.get('settings', None) is None:
            config['settings'] = ordereddict()
        config['settings']['pwd'] = self.base_path

        self._resolve_defaults(config)

        logger.debug(u"Parsed config", config=config)
        self._config = config

    def set_services(self, services):
        if not services:
            return
        remove_services = list(set(self._config['services']) - set(services))
        if remove_services:
            for service in remove_services:
                del self._config['services'][service]

    def check_requested_services(self, services):
        if not services:
            return
        missing_services = list(set(services) - set(self._config['services'].keys()))
        if missing_services:
            tense = '' if len(missing_services) <= 1 else 's'
            raise AnsibleContainerRequestException(
                "Requested service{} {} not defined in container.yml".format(tense, ', '.join(missing_services))
            )

    def _update_service_config(self, env, service_config):
        if isinstance(service_config, dict):
            dev_overrides = service_config.pop('dev_overrides', {})
            if env == 'dev':
                service_config.update(dev_overrides)
        if 'volumes' in service_config:
            # Expand ~, ${HOME}, ${PWD}, etc. found in the volume src path
            updated_volumes = []
            for volume in service_config['volumes']:
                vol_pieces = volume.split(':')
                vol_pieces[0] = path.normpath(path.expandvars(path.expanduser(vol_pieces[0])))
                updated_volumes.append(':'.join(vol_pieces))
            service_config['volumes'] = updated_volumes

        for engine_name in self.remove_engines:
            if engine_name in service_config:
                del service_config[engine_name]

    def _resolve_defaults(self, config):
        """
        Defaults are in the container.yml, overridden by any --var-file param given,
        and finally overridden by any AC_* environment variables.

        :param config: Loaded YAML config
        :return: None
        """
        if config.get('defaults'):
            # convert config['defaults'] to an ordereddict()
            tmp_defaults = ordereddict()
            tmp_defaults.update(copy.deepcopy(config['defaults']), relax=True)
            config['defaults'] = tmp_defaults
        defaults = config.setdefault('defaults', yaml.compat.ordereddict())

        vars_files = self.cli_vars_files or config.get('settings', {}).get('vars_files')
        if vars_files:
            for var_file in vars_files:
                defaults.update(self._get_variables_from_file(var_file=var_file), relax=True)

        logger.debug('The default type is', defaults=str(type(defaults)), config=str(type(config)))
        if PY2 and type(defaults) == ordereddict:
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

        :return ruamel.ordereddict
        '''
        logger.debug(u'Getting environment variables...')
        env_vars = ordereddict()
        for var, value in ((k, v) for k, v in os.environ.items()
                           if k.startswith('AC_')):
            env_vars[var[3:].lower()] = value
        logger.debug(u'Read environment variables', env_vars=env_vars)
        return env_vars

    def _get_variables_from_file(self, var_file):
        """
        Looks for file relative to base_path. If not found, checks relative to base_path/ansible.
        If file extension is .yml | .yaml, parses as YAML, otherwise parses as JSON.

        :return: ruamel.ordereddict
        """
        abspath = path.abspath(var_file)
        if not path.exists(abspath):
            dirname, filename = path.split(abspath)
            raise AnsibleContainerConfigException(
                u'Variables file "%s" not found. (I looked in "%s" for it.)' % (filename, dirname)
            )
        logger.debug("Use variable file: %s", abspath, file=abspath)

        if path.splitext(abspath)[-1].lower().endswith(('yml', 'yaml')):
            try:
                config = yaml.round_trip_load(open(abspath))
            except yaml.YAMLError as exc:
                raise AnsibleContainerConfigException(u"YAML exception: %s" % text_type(exc))
        else:
            try:
                config = json.load(open(abspath))
            except Exception as exc:
                raise AnsibleContainerConfigException(u"JSON exception: %s" % text_type(exc))
        return iteritems(config) if config else []

    TOP_LEVEL_WHITELIST = [
        'version',
        'settings',
        'volumes',
        'services',
        'defaults',
        'registries',
        'secrets'
    ]

    OPTIONS_KUBE_WHITELIST = []

    OPTIONS_OPENSHIFT_WHITELIST = []


    def _validate_config(self, config):
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.yml')
        schema = yaml.safe_load(open(schema_path))
        try:
            jsonschema.validate(config, schema)
        except jsonschema.ValidationError as e:
            logger.error('The container.yml file is invalid: %s', e.message)
            logger.debug(text_type(e))

    def _validate_project_name(self, project_name):
        """
        Validates that the project_name starts with an alphanumeric value.
        Raises an Exception if the project_name is invalid
        """
        if re.match(r"^[a-zA-Z0-9]{1}.*", project_name) == None:
            raise AnsibleContainerConfigException(u"Invalid project_name {0}\n".format(project_name)
                + u"The project_name has to start with an alphanumeric character.")

    def __getitem__(self, item):
        return self._config[item]

    def __iter__(self):
        return iter(self._config)

    def __len__(self):
        return len(self._config)


class AnsibleContainerConductorConfig(Mapping):
    _config = None

    @container.conductor_only
    def __init__(self, container_config, skip_services=False):
        self._skip_services = skip_services
        self._config = container_config
        self._templar = Templar(loader=None, variables={})
        self._process_defaults()
        self._process_top_level_sections()
        self._process_services()

    def _process_section(self, section_value, callback=None, templar=None):
        if not templar:
            templar = self._templar
        processed = ordereddict()
        for key, value in section_value.items():
            if isinstance(value, string_types):
                # strings can be templated
                processed[key] = templar.template(value)
                if isinstance(processed[key], AnsibleUnsafeText):
                    processed[key] = str(processed[key])
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
            self._config.get('defaults', ordereddict()),
            callback=lambda processed: self._templar.set_available_variables(
                dict(processed)))

    def _process_top_level_sections(self):
        self._config['settings'] = self._config.get('settings', yaml.compat.ordereddict())
        for section in ['volumes', 'registries', 'secrets']:
            logger.debug('Processing section...', section=section)
            setattr(self, section, dict(self._process_section(self._config.get(section, ordereddict()))))

    def _process_services(self):
        services = ordereddict()
        for service, service_data in self._config.get('services', ordereddict()).items():
            logger.debug('Processing service...', service=service, service_data=service_data)
            processed = ordereddict()
            if not self._skip_services:
                service_defaults = self.defaults.copy()
                for idx in range(len(service_data.get('volumes', []))):
                    # To mount the project directory, let users specify `$PWD` and
                    # have that filled in with the project path
                    service_data['volumes'][idx] = re.sub(r'\$(PWD|\{PWD\})', self._config['settings'].get('pwd'),
                                                          service_data['volumes'][idx])
                for role_spec in service_data.get('roles', []):
                    if isinstance(role_spec, dict):
                        # A role with parameters to run it with
                        role_spec_copy = copy.deepcopy(role_spec)
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
                logger.debug('Rendering service keys from defaults', service=service, defaults=service_defaults)
                services[service] = self._process_section(
                    processed,
                    templar=Templar(loader=None, variables=service_defaults)
                )
                services[service]['defaults'] = service_defaults
            else:
                services[service] = service_data
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
        return 5

    def __iter__(self):
        yield self.defaults
        yield self.registries
        yield self.volumes
        yield self.services
        yield self.secrets
