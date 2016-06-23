# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os
import datetime
import re

from .exceptions import (AnsibleContainerAlreadyInitializedException,
                         AnsibleContainerRegistryNotFoundException,
                         AnsibleContainerRegistryAttributeException)
from .utils import *
from .shipit.utils import create_path

from .shipit.constants import SHIPIT_PATH, SHIPIT_ROLES_DIR

class BaseEngine(object):
    engine_name = None
    orchestrator_name = None
    default_registry_url = ''
    default_registry_name = ''

    def __init__(self, base_path, project_name, params={}):
        self.base_path = base_path
        self.project_name = project_name
        self.config = get_config(base_path)
        logger.debug('Initialized with params: %s', params)
        self.params = params

        self.support_init = True
        self.supports_build = True
        self.supports_push = True
        self.supports_run = True


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
        After the build completed, did the build run successfully?

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

    def orchestrate_galaxy_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during galaxy calls.

        :return: dictionary
        """
        return {}

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

    def push_latest_image(self, host, url=None, namespace=None):
        """
        Push the latest built image for a host to a registry

        :param host: The host in the container.yml to push
        :param url: The url of the registry.
        :param namespace: The username or organization that owns the image repo
        :return: None
        """
        raise NotImplementedError()

    def get_config(self):
        raise NotImplementedError()

    def get_config_for_shipit(self, url=None, namespace=None):
        '''
        Get the configuration needed by cmdrun_shipit. Result should include
        the *options* attribute for each service, as it may contain cluster
        directives.

        :param url: URL to the registry.
        :param namepace: a namespace withing the registry. Typically a username or organization.
        :return: configuration dictionary
        '''
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


def cmdrun_build(base_path, engine_name, flatten=True, purge_last=True, rebuild=False,
                 ansible_options='', **kwargs):
    engine_args = kwargs.copy()
    engine_args.update(locals())
    engine_obj = load_engine(**engine_args)
    create_build_container(engine_obj, base_path)
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
        logger.info('Cleaning up Ansible Container builder...')
        builder_container_id = engine_obj.get_builder_container_id()
        engine_obj.remove_container_by_id(builder_container_id)


def cmdrun_run(base_path, engine_name, service=[], production=False, **kwargs):
    assert_initialized(base_path)
    engine_args = kwargs.copy()
    engine_args.update(locals())
    engine_obj = load_engine(**engine_args)
    with make_temp_dir() as temp_dir:
        hosts = service or (engine_obj.all_hosts_in_orchestration())
        engine_obj.orchestrate('run', temp_dir,
                               hosts=hosts)


def cmdrun_push(base_path, engine_name, username=None, password=None, email=None,
                url=None, namespace=None, push_to=None, **kwargs):
    assert_initialized(base_path)
    engine_args = kwargs.copy()
    engine_args.update(locals())
    engine_obj = load_engine(**engine_args)

    url, namespace = get_registry_url_and_namespace(engine_obj, registry_name=push_to, username=username, password=password,
                                                    email=email, url=url, namespace=namespace)

    logger.info('Pushing to "%s/%s' % (re.sub(r'/$', '', url), namespace))

    for host in engine_obj.hosts_touched_by_playbook():
        engine_obj.push_latest_image(host, url=url, namespace=namespace)
    logger.info('Done!')


def cmdrun_shipit(base_path, engine_name, username=None, password=None, email=None,
                  url=None, namespace=None, pull_from=None, **kwargs):
    engine_args = kwargs.copy()
    engine_args.update(locals())
    engine_obj = load_engine(**engine_args)
    shipit_engine_name = kwargs.pop('shipit_engine')
    project_name = os.path.basename(base_path).lower()
    pull_from = kwargs.get('pull_from')

    url, namespace = get_registry_url_and_namespace(engine_obj, registry_name=pull_from, username=username,
                                                    password=password, email=email, url=url, namespace=namespace)
    config = engine_obj.get_config_for_shipit(url=url, namespace=namespace)
    shipit_engine_obj = load_shipit_engine(AVAILABLE_SHIPIT_ENGINES[shipit_engine_name]['cls'],
                                           config=config,
                                           base_path=base_path,
                                           project_name=project_name)

    # create the roles path
    roles_path = os.path.join(base_path, SHIPIT_PATH, SHIPIT_ROLES_DIR)
    create_path(roles_path)

    # Use the build container to Initialize the role
    context = dict(
        roles_path=roles_path,
        role_name="%s_%s" % (project_name, shipit_engine_obj.name)
    )
    with make_temp_dir() as temp_dir:
        logger.info('Executing ansible-galaxy init %s' % project_name)
        engine_obj.orchestrate('galaxy', temp_dir, context=context)
        if not engine_obj.build_was_successful():
            logger.error('Role initialization failed.')
            logger.info('Cleaning up and removing build container...')
            builder_container_id = engine_obj.get_builder_container_id()
            engine_obj.remove_container_by_id(builder_container_id)
            return

    # create the role and sample playbook
    shipit_engine_obj.run()
    logger.info('Role %s created.' % project_name)

    if kwargs.get('save_config'):
        # generate and save the configuration templates
        config_path = shipit_engine_obj.save_config()
        logger.info('Saved configuration to %s' % config_path)


def create_build_container(container_engine_obj, base_path):
    assert_initialized(base_path)
    logger.info('(Re)building the Ansible Container image.')
    build_output = container_engine_obj.build_buildcontainer_image()
    for line in build_output:
        logger.debug(line)
    builder_img_id = container_engine_obj.get_builder_image_id()
    logger.info('Ansible Container image has ID %s', builder_img_id)
    return builder_img_id


def get_registry_url_and_namespace(engine_obj, registry_name=None, username=None, password=None, email=None,
                                   url=None, namespace=None):
    '''
    Given the login options, returns the url and namespace to use for image push and pull.

    Verifies user can authenticate when username is present (in which case login will prompt for missing password).
    If already authenticated and the auth data exists in the container's local config, then determines the username.

    Using what is provided + what is returned by login + container engine defaults, determine the correct url and
    namespace.

    :param engine_obj: container engine
    :param registry_name: optional registry key found in container.yml
    :param username: optional username for authentication
    :param password: optional password for authentication
    :param email: optional email for authentication
    :param url: optional url to the registry. if not provided, defaults to engine_obj.default_registry_url
    :param namespace: optional namespace. if not provided, defaults to username.
    :return: (url, namespace)
    '''
    config = engine_obj.config
    if registry_name:
        # expect to find push-to defined in container.yml with url and namespace attributes
        if not config.get('registries', {}).get(registry_name):
            raise AnsibleContainerRegistryNotFoundException("Registry %s not found in container.yml. Did you add it to "
                                                            "the registry key?")
        url = config['registries'][registry_name].get('url')
        if not url:
            raise AnsibleContainerRegistryAttributeException("Registry %s missing required attribute 'url'.")

        namespace = config['registries'][registry_name].get('namespace')

    if not url:
        url = engine_obj.default_registry_url

    # Check that we can authenticate to the registry and get the username
    username = engine_obj.registry_login(username=username, password=password,
                                         email=email, url=url)
    if not namespace:
        namespace = username

    return url, namespace

