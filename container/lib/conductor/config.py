# -*- coding: utf-8 -*-
from __future__ import absolute_import

from container.common.visibility import getLogger
logger = getLogger(__name__)

from collections import Mapping
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from ansible.template import Templar
from ruamel import yaml, ordereddict

from .utils import get_metadata_from_role, get_defaults_from_role

class AnsibleContainerConductorConfig(Mapping):
    _config = None

    def __init__(self, container_config):
        self._config = container_config
        self._templar = Templar(loader=None, variables={})

        self._process_defaults()
        self._process_top_level_sections()
        self._process_services()

    def _process_section(self, section_value, callback=None, templar=None):
        if not templar:
            templar = self._templar
        processed = ordereddict.ordereddict()
        for key, value in section_value.items():
            if isinstance(value, basestring):
                # strings can be templated
                processed[key] = templar.template(value)
            elif isinstance(value, (list, dict)):
                # if it's a dimensional structure, it's cheaper just to serialize
                # it, treat it like a template, and then deserialize it again
                buffer = StringIO()
                yaml.round_trip_dump(value, buffer)
                buffer = StringIO(templar.template(buffer.getvalue()))
                processed[key] = yaml.round_trip_load(buffer)
            else:
                # ints, booleans, etc.
                processed[key] = value
            if callback:
                callback(processed)
        return processed

    def _process_defaults(self):
        logger.debug('Processing defaults section...')
        self.defaults = self._process_section(
            self._config.get('defaults', ordereddict.ordereddict()),
            callback=lambda processed: self._templar.set_available_variables(
                dict(processed)))

    def _process_top_level_sections(self):
        for section in ['volumes', 'registries']:
            logger.debug('Processing section...', section=section)
            setattr(self, section,
                    self._process_section(self._config.get(
                        section, ordereddict.ordereddict())))

    def _process_services(self):
        services = ordereddict.ordereddict()
        for service, service_data in self._config.get(
                'services', ordereddict.ordereddict()).items():
            logger.debug('Processing service...', service=service)
            processed = ordereddict.ordereddict()
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
            logger.debug('Rendering service keys from defaults', defaults=service_defaults)
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








