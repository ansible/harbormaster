# -*- coding: utf-8 -*-
from __future__ import absolute_import

from container.common.visibility import getLogger
logger = getLogger(__name__)

import os
import hashlib

from jinja2 import Environment, FileSystemLoader
from ruamel import yaml, ordereddict
from ansible.playbook.role.include import RoleInclude
from ansible.vars import VariableManager
from ansible.parsing.dataloader import DataLoader


def jinja_render_to_temp(templates_path, template_file, temp_dir, dest_file, **context):
    j2_env = Environment(loader=FileSystemLoader(templates_path))
    j2_tmpl = j2_env.get_template(template_file)
    rendered = j2_tmpl.render(dict(temp_dir=temp_dir, **context))
    logger.debug('Rendered Jinja Template:', rendered=rendered.encode('utf8'))
    open(os.path.join(temp_dir, dest_file), 'wb').write(
        rendered.encode('utf8'))


def metadata_to_image_config(metadata):

    def ports_to_exposed_ports(list_of_ports):
        to_return = {}
        for port_spec in list_of_ports:
            exposed_ports = port_spec.rsplit(':')[-1]
            if '-' in exposed_ports:
                low, high = exposed_ports.split('-', 1)
                for port in range(int(low), int(high)+1):
                    to_return[str(port)] = {}
            else:
                to_return[exposed_ports] = {}
        return to_return

    def format_environment(environment):
        to_return = dict(
            LD_LIBRARY_PATH='',
            CPATH='',
            PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            PYTHONPATH=''
        )
        if isinstance(environment, list):
            environment = {k: v for (k, v) in
                           [item.split('=', 1) for item in environment]}
        to_return.update(environment)
        return ['='.join(tpl) for tpl in to_return.iteritems()]

    TRANSLATORS = {
        # Keys are the key found in the service_data
        # Values are a 2-tuple of the image config JSON key and a function to
        # convert the service_data value to the image config JSON value or None
        # if no translation is necessary

        'hostname': ('Hostname', None),
        'domainname': ('Domainname', None),
        'user': ('User', None),
        'ports': ('ExposedPorts', ports_to_exposed_ports),
        'environment': ('Env', format_environment),
        'command': ('Cmd', None),
        'working_dir': ('WorkingDir', None),
        'entrypoint': ('Entrypoint', None),
        'volumes': ('Volumes', lambda _list: {parts[0]:{}
                                              for parts in [v.split()
                                                            for v in _list]}),
        'labels': ('Labels', None),
        'onbuild': ('OnBuild', None)
    }

    config = dict(
        Hostname='',
        Domainname='',
        User='',
        ExposedPorts={},
        Env=[],
        Cmd='',
        WorkingDir='',
        Entrypoint=None,
        Volumes={},
        Labels={},
        OnBuild=[]
    )

    for metadata_key, (key, translator) in TRANSLATORS.iteritems():
        if metadata_key in metadata:
            config[key] = (translator(metadata[metadata_key]) if translator
                           else metadata[metadata_key])
    return config


def resolve_role_to_path(role_name):
    loader, variable_manager = DataLoader(), VariableManager()
    role_obj = RoleInclude.load(data=role_name, play=None,
                                variable_manager=variable_manager,
                                loader=loader)
    role_path = role_obj._role_path
    return role_path


def get_role_fingerprint(role_name):

    def hash_file(hash_obj, file_path):
        blocksize = 64 * 1024
        with open(file_path, 'rb') as ifs:
            while True:
                data = ifs.read(blocksize)
                if not data:
                    break
                hash_obj.update(data)
                hash_obj.update('::')

    def hash_dir(hash_obj, dir_path):
        for root, dirs, files in os.walk(dir_path, topdown=True):
            for file_path in files:
                abs_file_path = os.path.join(root, file_path)
                hash_obj.update(abs_file_path)
                hash_obj.update('::')
                hash_file(hash_obj, abs_file_path)

    def hash_role(hash_obj, role_path):
        # A role is easy to hash - the hash of the role content with the
        # hash of any role dependencies it has
        hash_dir(hash_obj, role_path)
        for dependency in get_dependencies_for_role(role_path):
            if dependency:
                dependency_path = resolve_role_to_path(dependency)
                hash_role(hash_obj, dependency_path)

    def get_dependencies_for_role(role_path):
        meta_main_path = os.path.join(role_path, 'meta', 'main.yml')
        meta_main = yaml.safe_load(open(meta_main_path))
        for dependency in meta_main.get('dependencies', []):
            yield dependency.get('role', None)

    hash_obj = hashlib.sha256()
    hash_role(hash_obj, resolve_role_to_path(role_name))
    return hash_obj.hexdigest()


def get_content_from_role(role_name, relative_path):
    role_path = resolve_role_to_path(role_name)
    metadata_file = os.path.join(role_path, relative_path)
    if os.path.exists(metadata_file):
        with open(metadata_file) as ifs:
            metadata = yaml.round_trip_load(ifs)
        return metadata
    return ordereddict.ordereddict()


def get_metadata_from_role(role_name):
    return get_content_from_role(role_name, os.path.join('meta', 'container.yml'))


def get_defaults_from_role(role_name):
    return get_content_from_role(role_name, os.path.join('defaults', 'main.yml'))
