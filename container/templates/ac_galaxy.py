#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import tempfile
import shutil
import os
import sys

import ansible.constants as C
from ansible.galaxy import Galaxy
from ansible.galaxy.role import GalaxyRole
from ansible.playbook.role.requirement import RoleRequirement
import ruamel.yaml

ANSIBLE_CONTAINER_PATH = '/ansible-container'

class FatalException(Exception): pass
class RoleException(Exception): pass

class MakeTempDir(object):
    temp_dir = None

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp()
        logger.debug('Using temporary directory %s...', self.temp_dir)
        return os.path.realpath(self.temp_dir)

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            logger.debug('Cleaning up temporary directory %s...', self.temp_dir)
            shutil.rmtree(self.temp_dir)
        except Exception, e:
            logger.exception('Failure cleaning up temp space')
            pass

class InCaseOfFail(object):
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir

    def __enter__(self):
        for yml_file in ['container.yml', 'main.yml', 'requirements.yml']:
            shutil.copyfile(os.path.join(ANSIBLE_CONTAINER_PATH, 'ansible', yml_file),
                            os.path.join(self.temp_dir, yml_file))

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.info('Undoing changes to .yml files')
            for yml_file in ['container.yml', 'main.yml', 'requirements.yml']:
                shutil.copyfile(
                    os.path.join(self.temp_dir, yml_file),
                    os.path.join(ANSIBLE_CONTAINER_PATH, 'ansible', yml_file))

class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self

def get_galaxy(tmp_dir, token):
    return Galaxy(AttrDict(api_server=C.GALAXY_SERVER,
                           ignore_certs=C.GALAXY_IGNORE_CERTS,
                           ignore_errors=False,
                           no_deps=False,
                           roles_path=[tmp_dir],
                           token=token))

def role_to_temp_space(role_req, galaxy):
    role_req_kwargs = RoleRequirement.role_yaml_parse(role_req.strip())
    role_obj = GalaxyRole(galaxy, **role_req_kwargs)
    installed = role_obj.install()
    return role_obj, installed

def get_container_yml_snippet(role_obj):
    container_yml_path = os.path.join(role_obj.path, 'meta', 'container.yml')
    if os.path.exists(container_yml_path):
        try:
            snippet = ruamel.yaml.round_trip_load(open(container_yml_path))
        except Exception, e:
            logger.exception('Error loading container.yml snippet for %s',
                             role_obj)
            return None
        logger.debug('Role %s is containerized', role_obj)
        try:
            assert isinstance(snippet, dict) and len(snippet) == 1
        except AssertionError:
            logger.exception('Role %s container.yml is malformed', role_obj)
            return None
        return snippet
    logger.debug('No %s found for %s, not containerized', container_yml_path,
                 role_obj)

def get_knobs_and_dials(role_obj):
    defaults_yml_path = os.path.join(role_obj.path, 'defaults', 'main.yml')
    if os.path.exists(defaults_yml_path):
        try:
            defaults = ruamel.yaml.round_trip_load(open(defaults_yml_path))
        except Exception, e:
            logger.exception('Error loading defaults/main.yml for %s',
                             role_obj)
        else:
            return defaults
    return {}

def update_container_yml(role_obj):
    snippet = get_container_yml_snippet(role_obj)
    if not snippet:
        return None
    container_yml_path = os.path.join(ANSIBLE_CONTAINER_PATH, 'ansible',
                                      'container.yml')
    try:
        container_yml = ruamel.yaml.round_trip_load(open(container_yml_path))
    except Exception, e:
        logger.exception('Could not load project ansible/container.yml')
        raise FatalException()

    # It can be None if left empty
    if not container_yml['services']:
        container_yml['services'] = {}
    services = container_yml['services']
    # The snippet should be a dictionary with one key
    new_service_key = snippet.keys()[0]
    if new_service_key in services:
        logger.error('Role defines service %s, but ansible/container.yml '
                     'already has a service with this name', new_service_key)
        raise RoleException()

    services[new_service_key] = snippet[new_service_key]
    try:
        ruamel.yaml.round_trip_dump(container_yml,
                                    stream=open(container_yml_path, 'w'))
    except Exception, e:
        logger.exception('Error updating ansible/container.yml')
        raise FatalException()
    return new_service_key

def update_main_yml(service, role_obj):
    defaults = get_knobs_and_dials(role_obj)
    main_yml_path = os.path.join(ANSIBLE_CONTAINER_PATH, 'ansible',
                                 'main.yml')
    main_yml = None
    try:
        main_yml = ruamel.yaml.round_trip_load(open(main_yml_path))
    except Exception, e:
        logger.exception('Could not load project ansible/main.yml')
        raise FatalException()

    if not main_yml:
        main_yml = [] 

    # this is a ruamel.ordereddict.OrderedDict
    # for readability, put the role name at the start of the dict
    defaults.insert(0, 'role', role_obj.name)

    snippet = {
        'hosts': service,
        'roles': [defaults]
    }
    main_yml.append(snippet)
    try:
        ruamel.yaml.round_trip_dump(main_yml,
                                    stream=open(main_yml_path, 'w'))
    except Exception, e:
        logger.exception('Error updating ansible/main.yml')
        raise FatalException()

def update_requirements_yml(role_obj):
    requirements_yml_path = os.path.join(ANSIBLE_CONTAINER_PATH, 'ansible',
                                         'requirements.yml')
    requirements = None
    if os.path.exists(requirements_yml_path):
        try:
            requirements = ruamel.yaml.round_trip_load(open(requirements_yml_path)) or []
        except Exception, e:
            logger.exception('Could not load project ansible/requirements.yml')
            raise FatalException()
    if not requirements:
        requirements = []
    for req in requirements:
        if req.get('src', '') == role_obj.src:
            logger.warning('Requirement %s already found in requirements.yml',
                           role_obj.name)
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
    except Exception, e:
        logger.exception('Error updating ansible/requirements.yml')
        raise FatalException()

def install(roles):
    roles_to_install = list(roles)
    with MakeTempDir() as temp_dir:
        galaxy = get_galaxy(temp_dir, None) # FIXME: support tokens
        roles_processed = []
        role_failure = False
        with InCaseOfFail(temp_dir):
            while roles_to_install:
                try:
                    role_to_install = roles_to_install.pop()
                    role_obj, installed = role_to_temp_space(role_to_install, galaxy)
                    if installed:
                        deps = role_obj.metadata.get('dependencies', [])
                        for dep in deps:
                            if dep not in roles_to_install + roles_processed:
                                roles_to_install.append(dep)
                        service = update_container_yml(role_obj)
                        if service:
                            update_main_yml(service, role_obj)
                        else:
                            logger.warning('Role %s is not Ansible Container enabled.',
                                           role_obj)
                        update_requirements_yml(role_obj)
                    roles_processed.append(role_to_install)
                except FatalException:
                    raise
                except RoleException:
                    role_failure = True
                    continue
    if role_failure:
        raise RoleException('One or more roles failed.')

if __name__ == '__main__':
    import argparse
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('roles', nargs='+', action='store')

    args = parser.parse_args()
    try:
        install(args.roles)
    except Exception, e:
        logger.error(unicode(e))
        sys.exit(1)


