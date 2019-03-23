# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .visibility import getLogger
logger = getLogger(__name__)

import os
import hashlib
import importlib
import json

from datetime import datetime
from distutils import dir_util
from jinja2 import Environment, FileSystemLoader
from ruamel import yaml
from six import iteritems, string_types, text_type


from ..exceptions import AnsibleContainerException, \
    AnsibleContainerNotInitializedException
from .temp import MakeTempDir
from . import _text as text
import container

if container.ENV == 'conductor':
    from ansible.playbook.role.include import RoleInclude
    try:
        from ansible.vars.manager import VariableManager
    except ImportError:
        # Prior to ansible/ansible@8f97aef1a365, this was not in its own module
        from ansible.vars import VariableManager
    from ansible.parsing.dataloader import DataLoader
    from ansible.playbook.play import Play
    from ansible.playbook.play_context import PlayContext
    from ansible.executor.play_iterator import PlayIterator
    from ansible.inventory.manager import InventoryManager
    from ansible.inventory.host import Host

__all__ = ['conductor_dir', 'make_temp_dir', 'get_config', 'assert_initialized',
           'create_path', 'jinja_template_path', 'jinja_render_to_temp',
           'metadata_to_image_config', 'create_role_from_templates',
           'resolve_role_to_path', 'generate_playbook_for_role',
           'get_role_fingerprint', 'get_content_from_role',
           'get_metadata_from_role', 'get_defaults_from_role', 'text',
           'ordereddict_to_list', 'list_to_ordereddict', 'modules_to_install',
           'roles_to_install', 'ansible_config_exists', 'create_file']

conductor_dir = os.path.dirname(container.__file__)
make_temp_dir = MakeTempDir

FILE_COPY_MODULES = ['synchronize', 'copy']


def get_config(base_path, vars_files=None, engine_name=None, project_name=None, vault_files=None, config_file=None):
    mod = importlib.import_module('.%s.config' % engine_name,
                                  package='container')
    return mod.AnsibleContainerConfig(base_path, vars_files=vars_files, engine_name=engine_name,
                                      project_name=project_name, vault_files=vault_files, config_file=config_file)


def resolve_config_path(base_path, config_file):
    if not config_file:
        raise AnsibleContainerNotInitializedException(
            "Missing config_file. This is a bug, as it should have defaulted to 'container.yml'. "
            "Please report this incident, so we can put a halt to such shinanigans!"
        )
    # The config file may live outside the project path. However, when no path specified, look for it in project path.
    if os.path.dirname(config_file):
        return config_file
    return os.path.join(base_path, config_file)


def assert_initialized(base_path, config_file=None):
    ansible_dir = os.path.normpath(base_path)
    container_file = resolve_config_path(base_path, config_file)
    if not all((
        os.path.exists(ansible_dir), os.path.isdir(ansible_dir),
        os.path.exists(container_file), os.path.isfile(container_file),
    )):
        raise AnsibleContainerNotInitializedException()


def create_path(path):
    try:
        os.makedirs(path)
    except OSError:
        pass
    except Exception as exc:
        raise AnsibleContainerException("Error: failed to create %s - %s" % (path, str(exc)))


def jinja_template_path():
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            '..',
            'templates'))


def jinja_render_to_temp(template_dir, template_file, temp_dir, dest_file, **context):
    j2_env = Environment(loader=FileSystemLoader(template_dir))
    j2_tmpl = j2_env.get_template(template_file)
    rendered = j2_tmpl.render(dict(temp_dir=temp_dir, **context))
    logger.debug('Rendered Jinja Template:', body=rendered.encode('utf8'))
    open(os.path.join(temp_dir, dest_file), 'wb').write(
        rendered.encode('utf8'))


def metadata_to_image_config(metadata):

    def ports_to_exposed_ports(list_of_ports):
        to_return = {}
        for port_spec in map(text_type, list_of_ports):
            exposed_ports = port_spec.rsplit(':', 1)[-1]
            protocol = 'tcp'
            if '/' in exposed_ports:
                exposed_ports, protocol = exposed_ports.split('/')
            if '-' in exposed_ports:
                low, high = exposed_ports.split('-', 1)
                for port in range(int(low), int(high)+1):
                    to_return['{}/{}'.format(str(port), protocol)] = {}
            else:
                to_return['{}/{}'.format(exposed_ports, protocol)] = {}
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
                           [item.split('=', 1) for item in environment if '=' in item]}
        to_return.update(environment)
        return ['='.join(map(text_type, tpl)) for tpl in iteritems(to_return)]

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
        #'volumes': ('Volumes', lambda _list: {parts[0]:{}
        #                                      for parts in [v.split()
        #                                                    for v in _list]}),
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
        #Volumes={},
        Labels={},
        OnBuild=[]
    )

    for metadata_key, (key, translator) in iteritems(TRANSLATORS):
        if metadata_key in metadata:
            config[key] = (translator(metadata[metadata_key]) if translator
                           else metadata[metadata_key])
    return config


def create_role_from_templates(role_name=None, role_path=None,
                               project_name=None, description=None):
    """
    Create a new role with initial files from templates.
    :param role_name: Name of the role
    :param role_path: Full path to the role
    :param project_name: Name of the project, or the base path name.
    :param description: One line description of the role.
    :return: None
    """
    context = locals()
    templates_path = os.path.join(conductor_dir, 'templates', 'role')
    timestamp = datetime.now().strftime('%Y%m%d%H%M%s')

    logger.debug('Role template location', path=templates_path)
    for rel_path, templates in [(os.path.relpath(path, templates_path), files)
                                for (path, _, files) in os.walk(templates_path)]:
        target_dir = os.path.join(role_path, rel_path)
        dir_util.mkpath(target_dir)
        for template in templates:
            template_rel_path = os.path.join(rel_path, template)
            target_name = template.replace('.j2', '')
            target_path = os.path.join(target_dir, target_name)
            if os.path.exists(target_path):
                backup_path = u'%s_%s' % (target_path, timestamp)
                logger.debug(u'Found existing file. Backing target to backup',
                    target=target_path, backup=backup_path)
                os.rename(target_path, backup_path)
            logger.debug("Rendering template for %s/%s" % (target_dir, template))
            jinja_render_to_temp(templates_path,
                                 template_rel_path,
                                 target_dir,
                                 target_name,
                                 **context)

    new_file_name = "main_{}.yml".format(datetime.today().strftime('%y%m%d%H%M%S'))
    new_tasks_file = os.path.join(role_path, 'tasks', new_file_name)
    tasks_file = os.path.join(role_path, 'tasks', 'main.yml')

    if os.path.exists(tasks_file):
        os.rename(tasks_file, new_tasks_file)


@container.conductor_only
def resolve_role_to_path(role):
    """
    Given a role definition from a service's list of roles, returns the file path to the role
    """
    loader = DataLoader()
    try:
        variable_manager = VariableManager(loader=loader)
    except TypeError:
        # If Ansible prior to ansible/ansible@8f97aef1a365
        variable_manager = VariableManager()
    role_obj = RoleInclude.load(data=role, play=None,
                                variable_manager=variable_manager,
                                loader=loader)
    return role_obj._role_path

@container.conductor_only
def generate_playbook_for_role(service_name, vars, role):
    playbook = [
        {'hosts': service_name,
         'vars': vars or {},
         'roles': [role],
         }
    ]

    if isinstance(role, dict) and 'gather_facts' in role:
        # Allow disabling gather_facts at the role level
        playbook[0]['gather_facts'] = role.pop('gather_facts')
    logger.debug('Playbook generated: %s', playbook)
    return playbook


def get_dependencies_for_role(role_path):
    meta_main_path = os.path.join(role_path, 'meta', 'main.yml')
    if os.path.exists(meta_main_path):
        meta_main = yaml.safe_load(open(meta_main_path))
        if meta_main:
            for dependency in meta_main.get('dependencies', []):
                yield dependency.get('role', None)


@container.conductor_only
def get_role_fingerprint(role, service_name, config_vars):
    """
    Given a role definition from a service's list of roles, returns a hexdigest based on the role definition,
    the role contents, and the hexdigest of each dependency
    """
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
                hash_obj.update(abs_file_path.encode('utf-8'))
                hash_obj.update('::')
                hash_file(hash_obj, abs_file_path)

    def hash_role(hash_obj, role_path):
        # Role content is easy to hash - the hash of the role content with the
        # hash of any role dependencies it has
        hash_dir(hash_obj, role_path)
        for dependency in get_dependencies_for_role(role_path):
            if dependency:
                dependency_path = resolve_role_to_path(dependency)
                hash_role(hash_obj, dependency_path)
        # However tasks within that role might reference files outside of the
        # role, like source code
        loader = DataLoader()
        var_man = VariableManager(loader=loader)
        play = Play.load(generate_playbook_for_role(service_name, config_vars, role)[0],
                         variable_manager=var_man, loader=loader)
        play_context = PlayContext(play=play)
        inv_man = InventoryManager(loader, sources=['%s,' % service_name])
        host = Host(service_name)
        iterator = PlayIterator(inv_man, play, play_context, var_man, config_vars)
        while True:
            _, task = iterator.get_next_task_for_host(host)
            if task is None: break
            if task.action in FILE_COPY_MODULES:
                src = task.args.get('src')
                if src is not None:
                    if not os.path.exists(src) or not src.startswith(('/', '..')): continue
                    src = os.path.realpath(src)
                    if os.path.isfile(src):
                        hash_file(hash_obj, src)
                    else:
                        hash_dir(hash_obj, src)

    hash_obj = hashlib.sha256()
    # Account for variables passed to the role by including the invocation string
    hash_obj.update((json.dumps(role) if not isinstance(role, string_types) else role) + '::')
    # Add each of the role's files and directories
    hash_role(hash_obj, resolve_role_to_path(role))
    return hash_obj.hexdigest()


@container.conductor_only
def get_content_from_role(role_name, relative_path):
    role_path = resolve_role_to_path(role_name)
    metadata_file = os.path.join(role_path, relative_path)
    if os.path.exists(metadata_file):
        with open(metadata_file) as ifs:
            metadata = yaml.round_trip_load(ifs)
        return metadata or yaml.compat.ordereddict()
    return yaml.compat.ordereddict()


@container.conductor_only
def get_metadata_from_role(role_name):
    return get_content_from_role(role_name, os.path.join('meta', 'container.yml'))


@container.conductor_only
def get_defaults_from_role(role_name):
    return get_content_from_role(role_name, os.path.join('defaults', 'main.yml'))

@container.host_only
def ordereddict_to_list(config):
    # If configuration top-level key is an orderedict, convert to list of tuples, providing a
    # means to preserve key order. Call prior to encoding a config dict.
    result = {}
    for key, value in iteritems(config):
        if isinstance(value, yaml.compat.ordereddict):
            result[key] = list(value.items())
        else:
            result[key] = value
    return result

@container.conductor_only
def list_to_ordereddict(config):
    # If configuration top-level key is a list, convert it to an ordereddict.
    # Call post decoding of a config dict.
    result = yaml.compat.ordereddict()
    for key, value in iteritems(config):
        if isinstance(value, list):
            result[key] = yaml.compat.ordereddict(value)
        else:
            result[key] = value
    return result

@container.host_only
def roles_to_install(base_path):
    path = os.path.join(base_path, 'requirements.yml')
    if os.path.exists(path) and os.path.isfile(path):
        roles = yaml.safe_load(open(path, 'r'))
        if roles:
            return True
    return False

@container.host_only
def modules_to_install(base_path):
    path = os.path.join(base_path, 'ansible-requirements.txt')
    if os.path.exists(path) and os.path.isfile(path):
        with open(path, 'r') as fs:
            for line in fs:
                if not line.strip().startswith('#'):
                    return True
    return False

@container.host_only
def ansible_config_exists(base_path):
    path = os.path.join(base_path, 'ansible.cfg')
    if os.path.exists(path) and os.path.isfile(path):
        return True
    return False

@container.host_only
def create_file(file_path, contents):
    if not os.path.exists(file_path):
        try:
            os.makedirs(os.path.dirname(file_path), mode=0o775)
        except Exception:
            pass

        try:
            with open(file_path, 'w') as fs:
                fs.write(contents)
        except Exception:
            raise
