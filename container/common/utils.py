# -*- coding: utf-8 -*-
from __future__ import absolute_import

from datetime import datetime

from ..common.visibility import getLogger
logger = getLogger(__name__)

import functools
import inspect
import os
import importlib

from jinja2 import Environment, FileSystemLoader
from distutils import dir_util

from container.common.exceptions import AnsibleContainerException, \
    AnsibleContainerNotInitializedException
from container.config import AnsibleContainerConfig
from container.common.temp import MakeTempDir


def log_runs(fn):
    @functools.wraps(fn)
    def __wrapped__(self, *args, **kwargs):
        logger.debug(
            u'Call: %s.%s' % (type(self).__name__, fn.__name__),
            # because log_runs is a decorator, we need to override the caller
            # line & function
            caller_func='%s.%s' % (type(self).__name__, fn.__name__),
            caller_line=inspect.getsourcelines(fn)[-1],
            args=args,
            kwargs=kwargs,
        )
        return fn(self, *args, **kwargs)
    return __wrapped__


CAPABILITIES = dict(
    BUILD='building container images',
    BUILD_CONDUCTOR='building the Conductor image',
    DEPLOY='pushing and orchestrating containers remotely',
    IMPORT='importing as Ansible Container project',
    LOGIN='authenticate with registry',
    PUSH='push images to registry',
    RUN='orchestrating containers locally',
 )

AVAILABLE_SHIPIT_ENGINES = {
    'kube': {
        'help': 'Generate a role that deploys to Kubernetes.',
        'cls': 'kubernetes'
    },
    'openshift': {
        'help': 'Generate a role that deploys to OpenShift Origin.',
        'cls': 'openshift'
    }
}


make_temp_dir = MakeTempDir

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
            'templates'))

def jinja_render_to_temp(templates_path, template_file, temp_dir, dest_file, **context):
    j2_env = Environment(loader=FileSystemLoader(templates_path))
    j2_tmpl = j2_env.get_template(template_file)
    rendered = j2_tmpl.render(dict(temp_dir=temp_dir, **context))
    logger.debug('Rendered Jinja Template:', rendered=rendered.encode('utf8'))
    open(os.path.join(temp_dir, dest_file), 'wb').write(
        rendered.encode('utf8'))


def get_config(base_path, var_file=None):
    return AnsibleContainerConfig(base_path, var_file=var_file)

def config_format_version(base_path, config_data=None):
    if not config_data:
        config_data = get_config(base_path)
    return int(config_data.pop('version', 1))

def assert_initialized(base_path):
    ansible_dir = os.path.normpath(base_path)
    container_file = os.path.join(ansible_dir, 'container.yml')
    if not all((
        os.path.exists(ansible_dir), os.path.isdir(ansible_dir),
        os.path.exists(container_file), os.path.isfile(container_file),
    )):
        raise AnsibleContainerNotInitializedException()

def get_latest_image_for(project_name, host, client):
    image_data = client.images(
        '%s-%s' % (project_name, host,)
    )
    try:
        latest_image_data, = [datum for datum in image_data
                              if '%s-%s:latest' % (project_name, host,) in
                              datum['RepoTags']]
        image_buildstamp = [tag for tag in latest_image_data['RepoTags']
                            if not tag.endswith(':latest')][0].split(':')[-1]
        image_id = latest_image_data['Id']
        return image_id, image_buildstamp
    except (IndexError, ValueError):
        # No previous image built
        return None, None

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
    templates_path = os.path.join(os.path.dirname(__file__), 'templates', 'role')
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
