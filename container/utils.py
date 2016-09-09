# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import importlib
from jinja2 import Environment, FileSystemLoader

from .exceptions import AnsibleContainerNotInitializedException
from .config import AnsibleContainerConfig
from .temp import MakeTempDir


__all__ = ['make_temp_dir',
           'jinja_template_path',
           'jinja_render_to_temp',
           'get_config',
           'config_format_version',
           'assert_initialized',
           'get_latest_image_for',
           'load_engine',
           'load_shipit_engine',
           'AVAILABLE_SHIPIT_ENGINES']


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


def jinja_template_path():
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            'templates'))


def jinja_render_to_temp(template_file, temp_dir, dest_file, **context):
    j2_tmpl_path = jinja_template_path()
    j2_env = Environment(loader=FileSystemLoader(j2_tmpl_path))
    j2_tmpl = j2_env.get_template(template_file)
    rendered = j2_tmpl.render(dict(temp_dir=temp_dir, **context))
    logger.debug('Rendered Jinja Template:')
    logger.debug(rendered.encode('utf8'))
    open(os.path.join(temp_dir, dest_file), 'w').write(
        rendered.encode('utf8'))


def get_config(base_path, var_file=None):
    return AnsibleContainerConfig(base_path, var_file=var_file)


def config_format_version(base_path, config_data=None):
    if not config_data:
        config_data = get_config(base_path)
    return int(config_data.pop('version', 1))


def assert_initialized(base_path, playbook='main.yml'):
    '''
    Raise exception if the ansible directory relative to base_path was not initialized.

    :param **kwargs:
    :return: None
    '''
    ansible_dir = os.path.normpath(os.path.join(base_path, 'ansible'))
    container_file = os.path.join(ansible_dir, 'container.yml')
    ansible_file = os.path.join(ansible_dir, 'main.yml')
    ansible_file_exists = True
    if not kwargs.get('playbook') and not (os.path.exists(ansible_file) and os.path.isfile(ansible_file)):
        # NOTE: if playbook option, then playbook may only be visible inside the build container
        ansible_file_exists = False
    if not os.path.exists(ansible_dir) or not os.path.isdir(ansible_dir):
        raise AnsibleContainerNotInitializedException(
            u"Expected to find directory {0}. Did you run the `init` command? "
            u"Are you in the correct directory?".format(ansible_dir)
        )
    if not os.path.exists(container_file) or not os.path.isfile(container_file):
        raise AnsibleContainerNotInitializedException(
            u"Expected to find {0}. Did you run the `init` command? "
            u"Are you in the correct directory?".format(container_file)
        )
    if not ansible_file_exists:
        raise AnsibleContainerNotInitializedException(
            u"Expected to find {0}. Are you in the correct directory? "
            u"Did you forget to specify `--playbook`?".format(ansible_file)
        )


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


def load_engine(engine_name='', base_path='', **kwargs):
    """
    Given a container engine_name, dynamically load the engine.

    :param engine_name: the string for the module containing the engine.py code
    :param base_path: the base path during operation
    :return: container.engine.BaseEngine
    """
    mod = importlib.import_module('container.%s.engine' % engine_name)
    project_name = os.path.basename(base_path).lower()
    logger.debug('Project name is %s', project_name)
    return mod.Engine(base_path, project_name, kwargs)


def load_shipit_engine(engine_class, **kwargs):
    '''
    Given a class name, dynamically load a shipit engine.

    :param engine_class: name of the shipit engine class
    :param kwargs: key/value args to pass to the new shipit engine obj.
    :return: shipit engine object
    '''
    try:
        engine_module = importlib.import_module(
            'container.shipit.%s.engine' % engine_class)
    except ImportError as exc:
        raise ImportError(
            'No shipit module for %s found - %s' % (engine_class, str(exc)))
    try:
        engine_cls = getattr(engine_module, 'ShipItEngine')
    except Exception as exc:
        raise ImportError('Error getting ShipItEngine for %s - %s' % (engine_class, str(exc)))

    return engine_cls(**kwargs)
