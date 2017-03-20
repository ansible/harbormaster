# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .visibility import getLogger
logger = getLogger(__name__)

import os
import importlib
import tempfile
import shutil
import hashlib
from datetime import datetime
from distutils import dir_util

from jinja2 import Environment, FileSystemLoader
from ruamel import yaml, ordereddict
try:
    from ansible.playbook.role.include import RoleInclude
    from ansible.vars import VariableManager
    from ansible.parsing.dataloader import DataLoader
    HAS_ANSIBLE = True
except ImportError:
    HAS_ANSIBLE = False

from .exceptions import AnsibleContainerConductorException

class MakeTempDir(object):
    temp_dir = None

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp()
        logger.debug('Using temporary directory', path=self.temp_dir)
        return os.path.realpath(self.temp_dir)

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            logger.debug('Cleaning up temporary directory',
                path=self.temp_dir)
            shutil.rmtree(self.temp_dir)
        except Exception:
            logger.error('Failure cleaning up temp space', path=self.temp_dir,
                    exc_info=True)

conductor_dir = os.path.normpath(os.path.dirname(__file__))

make_temp_dir = MakeTempDir

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


def create_role_from_templates(role_name=None, role_path=None,
                               project_name=None, description=None):
    '''
    Create a new role with initial files from templates.
    :param role_name: Name of the role
    :param role_path: Full path to the role
    :param project_name: Name of the project, or the base path name.
    :param description: One line description of the role.
    :return: None
    '''
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


def resolve_role_to_path(role_name):
    if not HAS_ANSIBLE:
        raise ImportError('Unable to import Ansible python API')
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
