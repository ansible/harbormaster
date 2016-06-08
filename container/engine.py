# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import datetime
import importlib

from .exceptions import AnsibleContainerAlreadyInitializedException
from .utils import *

class BaseEngine(object):
    engine_name = None
    orchestrator_name = None
    default_registry_url = ''

    def __init__(self, base_path, project_name):
        self.base_path = base_path
        self.project_name = project_name

    def all_hosts_in_orchestration(self):
        """
        List all hosts being orchestrated by the compose engine.

        :return: list of strings
        """
        raise NotImplementedError()

    def hosts_touched_by_playbook(self):
        """
        List all hosts touched by the execution of the build playbook.

        :return: list of strings
        """
        raise NotImplementedError()

    def build_buildcontainer_image(self):
        """
        Build in the container engine the builder container

        :return: generator of strings
        """
        raise NotImplementedError()

    def get_image_id_by_tag(self, name):
        """
        Query the engine to get an image identifier by tag

        :param name: the image name
        :return: the image identifier
        """
        raise NotImplementedError()

    def get_container_id_by_name(self, name):
        """
        Query the engine to get a container identifier by name

        :param name: the container name
        :return: the container identifier
        """
        raise NotImplementedError()

    def remove_container_by_name(self, name):
        """
        Remove a container from the engine given its name

        :param name: the name of the container to remove
        :return: None
        """
        raise NotImplementedError()

    def remove_container_by_id(self, id):
        """
        Remove a container from the engine given its identifier

        :param id: container identifier
        :return: None
        """
        raise NotImplementedError()

    def get_builder_image_id(self):
        """
        Query the enginer to get the builder image identifier

        :return: the image identifier
        """
        raise NotImplementedError()

    def get_builder_container_id(self):
        """
        Query the enginer to get the builder container identifier

        :return: the container identifier
        """
        raise NotImplementedError()

    def build_was_successful(self):
        """
        After the build was complete, did the build run successfully?

        :return: bool
        """
        raise NotImplementedError()

    def orchestrate(self, operation, temp_dir, hosts=[]):
        """
        Execute the compose engine.

        :param operation: One of build, run, or listhosts
        :param temp_dir: A temporary directory usable as workspace
        :param hosts: (optional) A list of hosts to limit orchestration to
        :return: The exit status of the builder container (None if it wasn't run)
        """
        raise NotImplementedError()

    def orchestrate_build_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during build.

        :return: dictionary
        """
        raise NotImplementedError()

    def orchestrate_run_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during run.

        :return: dictionary
        """
        raise NotImplementedError()

    def orchestrate_listhosts_args(self):
        """
        Provide extra arguments to provide the orchestrator during listhosts.

        :return: dictionary
        """
        raise NotImplementedError()

    def post_build(self, host, version, flatten=True, purge_last=True):
        """
        After orchestrated build, prepare an image from the built container.

        :param host: the name of the host in the orchestration file
        :param version: the version tag for the resultant image
        :param flatten: whether to flatten the resulatant image all the way
        :param purge_last: whether to purge the last version of the image in the engine
        :return: None
        """
        raise NotImplementedError()

    def registry_login(self, username=None, password=None, email=None, url=None):
        """
        Logs into registry for this engine

        :param username: Username to login with
        :param password: Password to login with - None to prompt user
        :param email: Email address to login with
        :param url: URL of registry - default defined per backend
        :return: None
        """
        raise NotImplementedError()

    def currently_logged_in_registry_user(self, url):
        """
        Gets logged in user from configuration for a URL for the registry for
        this engine.

        :param url: URL
        :return: (username, email) tuple
        """
        raise NotImplementedError()

    def push_latest_image(self, host, username):
        """
        Push the latest built image for a host to a registry

        :param host: The host in the container.yml to push
        :param username: The username to own the pushed image
        :return: None
        """
        raise NotImplementedError()

    def get_config(self):
        raise NotImplementedError()


def cmdrun_init(base_path, **kwargs):
    container_dir = os.path.normpath(
        os.path.join(base_path, 'ansible'))
    container_cfg = os.path.join(container_dir, 'container.yml')
    if os.path.exists(container_cfg):
        raise AnsibleContainerAlreadyInitializedException()
    if not os.path.exists(container_dir):
        os.mkdir(container_dir)
    template_dir = os.path.join(jinja_template_path(), 'ansible')
    for tmpl_filename in os.listdir(template_dir):
        jinja_render_to_temp('ansible/%s' % tmpl_filename,
                             container_dir,
                             tmpl_filename.replace('.j2', ''))
    logger.info('Ansible Container initialized.')


def cmdrun_build(base_path, engine, flatten=True, purge_last=True, rebuild=False,
                 **kwargs):
    assert_initialized(base_path)
    engine_obj = load_engine(engine, base_path)
    logger.info('(Re)building the Ansible Container image.')
    build_output = engine_obj.build_buildcontainer_image()
    for line in build_output:
        logger.debug(line)

    builder_img_id = engine_obj.get_builder_image_id()
    logger.info('Ansible Container image has ID %s', builder_img_id)
    with make_temp_dir() as temp_dir:
        logger.info('Starting %s engine to build your images...'
                    % engine_obj.orchestrator_name)
        touched_hosts = engine_obj.hosts_touched_by_playbook()
        engine_obj.orchestrate('build', temp_dir, context=dict(rebuild=rebuild))
        if not engine_obj.build_was_successful():
            logger.error('Ansible playbook run failed.')
            logger.info('Cleaning up Ansible Container builder...')
            builder_container_id = engine_obj.get_builder_container_id()
            engine_obj.remove_container_by_id(builder_container_id)
            return
        # Cool - now export those containers as images
        version = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
        logger.info('Exporting built containers as images...')
        for host in touched_hosts:
            engine_obj.post_build(host, version, flatten=flatten, purge_last=purge_last)
        for host in set(engine_obj.all_hosts_in_orchestration()) - set(touched_hosts):
            logger.info('Cleaning up %s build container...', host)
            engine_obj.remove_container_by_name(host)
        logger.info('Cleaning up Ansible Container builder...')
        builder_container_id = engine_obj.get_builder_container_id()
        engine_obj.remove_container_by_id(builder_container_id)


def cmdrun_run(base_path, engine, service=[], use_base_images=False, **kwargs):
    assert_initialized(base_path)
    engine_obj = load_engine(engine, base_path)
    with make_temp_dir() as temp_dir:
        hosts = service or ([] if use_base_images
                            else engine_obj.all_hosts_in_orchestration())
        engine_obj.orchestrate('run', temp_dir,
                               hosts=hosts,
                               context=dict(use_base_images=use_base_images))


def cmdrun_push(base_path, engine, username=None, password=None, email=None,
                url=None, **kwargs):
    assert_initialized(base_path)
    engine_obj = load_engine(engine, base_path)

    username = engine_obj.registry_login(username=username, password=password,
                                         email=email, url=url)

    logger.info('Pushing to repository for user %s', username)
    for host in engine_obj.hosts_touched_by_playbook():
        engine_obj.push_latest_image(host, username)
    logger.info('Done!')


def cmdrun_shipit(base_path, engine, **kwargs):
    shipit_engine = kwargs.pop('shipit_engine')
    try:
        engine_module = importlib.import_module('container.shipit.%s.engine' % shipit_engine)
        engine_cls = getattr(engine_module, 'ShipItEngine')
    except ImportError:
        raise ImportError('No shipit module for %s found.' % shipit_engine)
    else:
        shipit_engine_obj = engine_cls(base_path)

    project_name = os.path.basename(base_path).lower()
    engine_obj = load_engine(engine, base_path)
    config = engine_obj.get_config()
    create_templates = kwargs.pop('save_config')
    shipit_engine_obj.run(config=config, project_name=project_name,
                          project_dir=base_path, create_templates=create_templates)
