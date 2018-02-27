# -*- coding: utf-8 -*-
from __future__ import absolute_import

import shutil
import os

import ansible.constants as C
from ansible.galaxy import Galaxy
from ansible.galaxy.role import GalaxyRole
from ansible.playbook.role.requirement import RoleRequirement

import ruamel.yaml
from ruamel.yaml.comments import CommentedMap
from .temp import MakeTempDir

from container import exceptions
from container.utils.visibility import getLogger

logger = getLogger(__name__)

ANSIBLE_CONTAINER_PATH = '/_src'


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class InCaseOfFail(object):
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir

    def __enter__(self):
        for yml_file in ['container.yml', 'requirements.yml']:
            if os.path.isfile(os.path.join(ANSIBLE_CONTAINER_PATH, yml_file)):
                shutil.copyfile(os.path.join(ANSIBLE_CONTAINER_PATH, yml_file),
                                os.path.join(self.temp_dir, yml_file))

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.info('Undoing changes to .yml files')
            for yml_file in ['container.yml', 'requirements.yml']:
                if os.path.isfile(os.path.join(self.temp_dir, yml_file)):
                    shutil.copyfile(
                        os.path.join(self.temp_dir, yml_file),
                        os.path.join(ANSIBLE_CONTAINER_PATH, yml_file))


class AnsibleContainerGalaxy(object):
    _galaxy = None

    def install(self, roles):
        roles_to_install = list(roles)
        with MakeTempDir() as temp_dir:
            self._galaxy = Galaxy(AttrDict(api_server=C.GALAXY_SERVER,
                                           ignore_certs=C.GALAXY_IGNORE_CERTS,
                                           ignore_errors=False,
                                           no_deps=False,
                                           roles_path=[temp_dir],
                                           token=None))     # FIXME: support tokens
            roles_processed = []
            role_failure = False
            with InCaseOfFail(temp_dir):
                while roles_to_install:
                    try:
                        role_to_install = roles_to_install.pop()
                        role_obj, installed = self._role_to_temp_space(role_to_install)
                        if installed:
                            deps = role_obj.metadata.get('dependencies', [])
                            for dep in deps:
                                if dep not in roles_to_install + roles_processed:
                                    roles_to_install.append(dep)
                            self._update_container_yml(role_obj)
                            self._update_requirements_yml(role_obj)
                        roles_processed.append(role_to_install)
                    except exceptions.AnsibleContainerGalaxyFatalException as exc:
                        logger.error(exc)
                        raise
                    except exceptions.AnsibleContainerGalaxyRoleException as exc:
                        logger.error(exc)
                        role_failure = True
                        continue
        if role_failure:
            raise exceptions.AnsibleContainerGalaxyRoleException('One or more roles failed.')

    def _role_to_temp_space(self, role_req):
        role_req_kwargs = RoleRequirement.role_yaml_parse(role_req.strip())
        role_obj = GalaxyRole(self._galaxy, **role_req_kwargs)
        installed = role_obj.install()
        return role_obj, installed

    @staticmethod
    def _get_container_yml_snippet(role_obj):
        container_yml_path = os.path.join(role_obj.path, 'meta', 'container.yml')
        snippet = None
        if not os.path.exists(container_yml_path):
            logger.debug('No %s found for %s, not containerized' % (container_yml_path, role_obj.name))
            return snippet
        try:
            snippet = ruamel.yaml.round_trip_load(open(container_yml_path))
        except Exception:
            logger.exception('Error loading container.yml snippet for %s' % role_obj.name)
            return None
        logger.debug('Role %s is containerized', role_obj)
        try:
            assert isinstance(snippet, dict) and len(snippet) > 0
        except AssertionError:
            logger.exception('Role %s container.yml is malformed' % role_obj.name)
            return None
        return snippet

    @staticmethod
    def _get_knobs_and_dials(role_obj):
        defaults_yml_path = os.path.join(role_obj.path, 'defaults', 'main.yml')
        if os.path.exists(defaults_yml_path):
            try:
                defaults = ruamel.yaml.round_trip_load(open(defaults_yml_path))
            except Exception as exc:
                logger.exception('Error loading defaults/main.yml for %s - %s' % (role_obj.name, str(exc)))
            else:
                if not defaults:
                    defaults = CommentedMap()
                return defaults
        return CommentedMap()

    def _update_container_yml(self, role_obj):
        snippet = self._get_container_yml_snippet(role_obj)
        if not snippet:
            return None
        container_yml_path = os.path.join(ANSIBLE_CONTAINER_PATH, 'container.yml')
        try:
            container_yml = ruamel.yaml.round_trip_load(open(container_yml_path))
        except Exception as exc:
            raise exceptions.AnsibleContainerGalaxyFatalException('Failed to load container.yml: %s' % str(exc))

        if not container_yml['services']:
            container_yml['services'] = {}
        services = container_yml['services']
        new_service_key = role_obj.name.split('.', 1)[-1]
        if new_service_key in services:
            raise exceptions.AnsibleContainerGalaxyRoleException(
                'Role defines service %s, but container.yml already has a service with this name' % new_service_key)

        # Add role name to the service's list of roles
        services[new_service_key] = {}
        if not services[new_service_key].get('roles'):
            services[new_service_key]['roles'] = []
        if role_obj.name not in services[new_service_key]['roles']:
            services[new_service_key]['roles'].append(role_obj.name)

        try:
            ruamel.yaml.round_trip_dump(container_yml,
                                        stream=open(container_yml_path, 'w'))
        except Exception as exc:
            raise exceptions.AnsibleContainerGalaxyFatalException('Error updating container.yml - %s' % str(exc))
        return new_service_key

    def _update_requirements_yml(self, role_obj):
        requirements_yml_path = os.path.join(ANSIBLE_CONTAINER_PATH, 'requirements.yml')
        requirements = None
        if os.path.exists(requirements_yml_path):
            try:
                requirements = ruamel.yaml.round_trip_load(open(requirements_yml_path)) or []
            except Exception as exc:
                raise exceptions.AnsibleContainerGalaxyFatalException(
                    'Could not load project requirements.yml - %s' % str(exc))
        if not requirements:
            requirements = []
        for req in requirements:
            if req.get('src', '') == role_obj.src:
                logger.warning('Requirement %s already found in requirements.yml' % role_obj.name)
                return
        role_def = {}
        role_def[u'src'] = role_obj.src
        if role_obj.version and role_obj.version != 'master':
            role_def[u'version'] = role_obj.version
        if role_obj.scm:
            role_def[u'scm'] = role_obj.scm
        if role_obj.name and role_obj.name != role_obj.src:
            role_def[u'name'] = role_obj.name
        requirements.append(role_def)
        try:
            ruamel.yaml.round_trip_dump(requirements,
                                        stream=open(requirements_yml_path, 'w'))
        except Exception as exc:
            raise exceptions.AnsibleContainerGalaxyFatalException('Error updating requirements.yml')
