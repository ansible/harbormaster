# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import json
import yaml
import re

from jinja2 import Environment, FileSystemLoader
from collections import Mapping
from .exceptions import AnsibleContainerConfigException
from .filters import LookupLoader, FilterLoader
from .temp import MakeTempDir as make_temp_dir

# TODO: Actually do some schema validation


class AnsibleContainerConfig(Mapping):
    _config = {}
    base_path = None
    lookup_loader = LookupLoader()
    filter_loader = FilterLoader()

    def __init__(self, base_path, var_file=None):
        self.base_path = base_path
        self.var_file = var_file
        self.config_path = os.path.join(self.base_path, 'ansible/container.yml')
        self.all_filters = self.filter_loader.all()
        self.set_env('prod')

    def set_env(self, env):
        '''
        Loads config from container.yml, performs Jinja templating, and stores the resulting dict to self._config.

        :param env: string of either 'dev' or 'prod'. Indicates 'dev_overrides' handling.
        :return: None
        '''
        assert env in ['dev', 'prod']
        context = self._get_variables()
        config = self._render_template(context=context)
        try:
            config = yaml.safe_load(config)
        except yaml.YAMLError as exc:
            raise AnsibleContainerConfigException(u"Parsing container.yml - %s" % str(exc))
        if config.get('defaults'):
            del config['defaults']

        # definition is one of services, volumes, networks for Docker Compose v2
        for definition, configuration in config.iteritems():
            if definition in ['services', 'volumes', 'networks']:
                for arg, param in configuration.items():
                    if not param or isinstance(param, basestring):
                        raise AnsibleContainerConfigException(u"Error: no definition found in container.yml for {} definition - {}.".format(definition, arg))
                    if isinstance(param, dict):
                        dev_overrides = param.pop('dev_overrides', {})
                        if env == 'dev':
                            param.update(dev_overrides)

        logger.debug(u"Config:\n%s" % json.dumps(config,
                                                 sort_keys=True,
                                                 indent=4,
                                                 separators=(',', ': ')))
        self._config = config

    def _lookup(self, name, *args, **kwargs):
        lookup_instance = self.lookup_loader.get(name)
        wantlist = kwargs.pop('wantlist', False)
        try:
            ran = lookup_instance.run(args, {}, **kwargs)
        except Exception as exc:
            raise AnsibleContainerConfigException("Error in filter %s - %s" % (name, exc))

        if ran and not wantlist:
            ran = ','.join(ran)
        return ran

    def _render_template(self, context=None, path=None, template='container.yml'):
        '''
        Apply Jinja template rendering to a given template. If no template provided, template ansible/container.yml

        :param template_vars: dict providing Jinja context
        :return: dict
        '''
        if not context:
            context = dict()
        if not path:
            path = os.path.join(self.base_path, 'ansible')
        j2_env = Environment(loader=FileSystemLoader(path))
        j2_env.globals['lookup'] = self._lookup
        j2_env.filters.update(self.all_filters)
        j2_tmpl = j2_env.get_template(template)
        return j2_tmpl.render(**context).encode('utf8')

    def _get_variables(self):
        '''
        Resolve variables by creating an empty dict and updating it first with the 'defaults' section in the config,
        then any variables from var_file, and finally any AC_* environment variables. Returns the resulting dict.

        :return: dict
        '''
        new_vars = {}
        new_vars.update(self._get_defaults())
        if self.var_file:
            logger.debug('Reading variables from var file...')
            file_vars = self._get_variables_from_file(self.var_file, context=new_vars)
            new_vars.update(file_vars)
        new_vars.update(self._get_environment_variables())
        logger.debug(u'Template variables:\n %s' % json.dumps(new_vars,
                                                              sort_keys=True,
                                                              indent=4,
                                                              separators=(',', ': ')))
        return new_vars

    def _get_defaults(self):
        '''
        Parse the optional 'defaults' section of container.yml

        :return: dict
        '''
        defaults = {}
        default_lines = ['defaults:']
        found = False
        sections = [u'version:', u'services:', u'registries:']
        try:
            with open(self.config_path, 'r') as f:
                for line in f:
                    if re.search(r'^defaults:', line):
                        found = True
                        continue
                    if found:
                        if re.sub(u'\n', '', line) not in sections:
                            default_lines.append(re.sub(u'\n', '', line))
                        else:
                            break
        except (OSError, IOError):
            raise AnsibleContainerConfigException(u"Failed to open %s. Are you in the correct directory?" %
                                                  self.config_path)

        if len(default_lines) > 1:
            # re-assemble the defaults section, template, and parse as yaml
            with make_temp_dir() as temp_dir:
                with open(os.path.join(temp_dir, 'defaults.txt'), 'w') as f:
                    f.write(u'\n'.join(default_lines))
                default_section = self._render_template(context={}, path=temp_dir, template='defaults.txt')
            try:
                config = yaml.safe_load(default_section)
                defaults.update(config.get('defaults'))
            except yaml.YAMLError as exc:
                raise AnsibleContainerConfigException(u"Parsing container.yml - %s" % str(exc))
        logger.debug(u"Default vars:")
        logger.debug(json.dumps(defaults, sort_keys=True, indent=4, separators=(',', ': ')))
        return defaults

    def _get_environment_variables(self):
        '''
        Look for any environment variables that start with 'AC_'. Returns dict of key:value pairs, where the
        key is the result of removing 'AC_' from the variable name and converting the remainder to lowercase.
        For example, 'AC_DEBUG=1' becomes 'debug: 1'.

        :return dict
        '''
        logger.debug(u'Getting environment variables...')
        new_vars = {}
        for var, value in os.environ.iteritems():
            matches = re.match(r'^AC_(.+)$', var)
            if matches:
                new_vars[matches.group(1).lower()] = value
        return new_vars

    def _get_variables_from_file(self, file, context=None):
        '''
        Looks for file relative to base_path. If not found, checks relative to base_path/ansible.
        If file extension is .yml | .yaml, parses as YAML, otherwise parses as JSON.

        :param file: string: path relative to base_path or base_path/ansible.
        :param context: dict of any available default variables
        :return: dict
        '''
        file_path = os.path.abspath(file)
        path = os.path.dirname(file_path)
        name = os.path.basename(file_path)
        if not os.path.isfile(file_path):
            path = self.base_path
            file_path = os.path.normpath(os.path.join(self.base_path, file))
            name = os.path.basename(file_path)
            if not os.path.isfile(file_path):
                path = os.path.join(self.base_path, 'ansible')
                file_path = os.path.normpath(os.path.join(path, file))
                name = os.path.basename(file_path)
                if not os.path.isfile(file_path):
                    raise AnsibleContainerConfigException(u"Unable to locate %s. Provide a path relative to %s or %s." % (
                                                          file, self.base_path, os.path.join(self.base_path, 'ansible')))
        logger.debug("Use variable file: %s" % file_path)
        data = self._render_template(context=context, path=path, template=name)

        if name.endswith('yml') or name.endswith('yaml'):
            try:
                config = yaml.safe_load(data)
            except yaml.YAMLError as exc:
                raise AnsibleContainerConfigException(u"YAML exception: %s" %  str(exc))
        else:
            try:
                config = json.loads(data)
            except Exception as exc:
                raise AnsibleContainerConfigException(u"JSON exception: %s" % str(exc))
        return config

    def __getitem__(self, item):
        return self._config.get(item)

    def __iter__(self):
        return iter(self._config)

    def __len__(self):
        return len(self._config)

