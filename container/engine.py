# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

import logging

logger = logging.getLogger(__name__)

import io
import os
import datetime
import re
import sys
import gzip
import tarfile

import requests
from six.moves.urllib.parse import urljoin

from .exceptions import AnsibleContainerAlreadyInitializedException, \
                        AnsibleContainerRegistryAttributeException, \
                        AnsibleContainerHostNotTouchedByPlaybook
from .utils import *
from . import __version__

REMOVE_HTTP = re.compile('^https?://')

class BaseEngine(object):
    engine_name = None
    orchestrator_name = None
    default_registry_url = ''
    default_registry_name = ''

    def __init__(self, base_path, project_name, params={}):
        self.base_path = base_path
        self.project_name = project_name
        self.var_file = params.get('var_file')
        self.config = get_config(base_path, var_file=self.var_file)
        self.params = params
        self.support_init = True
        self.supports_build = True
        self.supports_push = True
        self.supports_run = True

        logger.debug('Initialized with params: %s', params)


    def all_hosts_in_orchestration(self):
        """
        List all hosts being orchestrated by the compose engine.

        :return: list of strings
        """
        raise NotImplementedError()

    def hosts_touched_by_playbook(self):
        """
        List all hosts touched by the execution of the build playbook.

        :return: frozenset of strings
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

    def orchestrate_install_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during install calls.

        :return: dictionary
        """
        return {}

    def orchestrate_listhosts_args(self):
        """
        Provide extra arguments to provide the orchestrator during listhosts.

        :return: dictionary
        """
        raise NotImplementedError()

    def terminate(self, operation, temp_dir, hosts=[]):
        """
        Stop, remove containers deployed by `orchestrate`.

        :return: dictionary
        """
        raise NotImplementedError()

    def terminate_stop_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during stop.

        :return: dictionary
        """
        return NotImplementedError

    def restart(self, operation, temp_dir, hosts=[]):
        """
        Restart containers deployed by `orchestrate`, deploys if not deployed

        :param operation: 'restart'
        :param temp_dir: A temporary directory usable as workspace
        :param hosts: (optional) A list of hosts to limit orchestration to
        """

        return NotImplementedError

    def restart_restart_extra_args(self):
        """
        Provide extra arguments to provide the orchestrator during restart.

        :return: dictionary
        """
        return NotImplementedError

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

    def push_latest_image(self, host, url=None, namespace=None, tag=None):
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

    def get_config_for_shipit(self, url=None, namespace=None, tag=None):
        '''
        Get the configuration needed by cmdrun_shipit. Result should include
        the *options* attribute for each service, as it may contain cluster
        directives.

        :param url: URL to the registry.
        :param namepace: a namespace withing the registry. Typically a username or organization.
        :return: configuration dictionary
        '''
        raise NotImplementedError()

    def print_version_info(self):
        '''
        Output to stdout version information about this engine and orchestrator.

        :return: None
        '''


def cmdrun_init(base_path, project=None, **kwargs):
    if project:
        if os.listdir(base_path):
            raise AnsibleContainerAlreadyInitializedException(
                u'The init command can only be run in an empty directory.')
        try:
            namespace, name = project.split('.', 1)
        except ValueError:
            raise ValueError(u'Invalid project name: %r; use '
                             u'"username.project" style syntax.' % project)
        galaxy_base_url = kwargs.pop('server')
        response = requests.get(urljoin(galaxy_base_url, '/api/v1/roles/'),
                                params={'role_type': 'APP',
                                        'namespace': namespace,
                                        'name': name},
                                headers={'Accepts': 'application/json'})
        try:
            response.raise_for_status()
        except requests.RequestException as e:
            raise requests.RequestException(u'Could not find %r on Galaxy '
                                            u'server %r: %r' % (project,
                                                                galaxy_base_url,
                                                                e))
        if not response.json()['count']:
            raise ValueError(u'Could not find %r on Galaxy '
                             u'server %r: No such container app' % (project,
                                                                    galaxy_base_url))
        container_app_data = response.json()['results'][0]
        if not all([container_app_data[k] for k in ['github_user',
                                                    'github_repo']]):
            raise ValueError(u'Container app %r does not have a GitHub URL' % project)
        archive_url = u'https://github.com/%s/%s/archive/%s.tar.gz' % (
            container_app_data['github_user'],
            container_app_data['github_repo'],
            container_app_data['github_branch'] or u'master'
        )
        archive = requests.get(archive_url)
        try:
            archive.raise_for_status()
        except requests.RequestException as e:
            raise requests.RequestException(u'Could not get archive at '
                                            u'%r: %r' % (archive_url, e))
        faux_file = io.BytesIO(archive.content)
        gz_obj = gzip.GzipFile(fileobj=faux_file)
        tar_obj = tarfile.TarFile(fileobj=gz_obj)
        members = tar_obj.getmembers()
        # now we do the actual extraction to the path
        for member in members:
            # we only extract files, and remove any relative path
            # bits that might be in the file for security purposes
            # and drop the leading directory, as mentioned above
            if member.isreg() or member.issym():
                parts = member.name.split(os.sep)[1:]
                final_parts = []
                for part in parts:
                    if part != '..' and '~' not in part and '$' not in part:
                        final_parts.append(part)
                member.name = os.path.join(*final_parts)
                tar_obj.extract(member, base_path)
        logger.info(u'Ansible Container initialized from Galaxy container app %r', project)
    else:
        container_dir = os.path.normpath(
            os.path.join(base_path, 'ansible'))
        container_cfg = os.path.join(container_dir, 'container.yml')
        if os.path.exists(container_cfg):
            raise AnsibleContainerAlreadyInitializedException()
        if not os.path.exists(container_dir):
            os.mkdir(container_dir)
        template_dir = os.path.join(jinja_template_path(), 'ansible')
        context = {
            u'ansible_container_version': __version__
        }
        for tmpl_filename in os.listdir(template_dir):
            jinja_render_to_temp('ansible/%s' % tmpl_filename,
                                 container_dir,
                                 tmpl_filename.replace('.j2', ''),
                                 **context)
        logger.info('Ansible Container initialized.')


def cmdrun_build(base_path, engine_name, flatten=True, purge_last=True, local_builder=False,
                 rebuild=False, service=None, ansible_options='', save_build_container=False,
                 roles_path=None, **kwargs):
    engine_args = kwargs.copy()
    engine_args.update(locals())
    engine_obj = load_engine(**engine_args)
    try:
        builder_img_id = engine_obj.get_image_id_by_tag(engine_obj.builder_container_img_tag)
    except NameError:
        if local_builder:
            create_build_container(engine_obj, base_path)
    with make_temp_dir() as temp_dir:
        logger.info('Starting %s engine to build your images...'
                    % engine_obj.orchestrator_name)
        touched_hosts = set(engine_obj.hosts_touched_by_playbook())
        if service:
            touched_hosts &= set(service)
            if not touched_hosts:
                raise AnsibleContainerHostNotTouchedByPlaybook()
        engine_obj.orchestrate('build', temp_dir, context=dict(rebuild=rebuild))
        if not engine_obj.build_was_successful():
            logger.error('Ansible playbook run failed.')
            if not save_build_container:
                logger.info('Cleaning up Ansible Container builder...')
                builder_container_id = engine_obj.get_builder_container_id()
                engine_obj.remove_container_by_id(builder_container_id)
            raise RuntimeError(u'Ansible build failed')
        # Cool - now export those containers as images
        version = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
        logger.info('Exporting built containers as images...')
        for host in touched_hosts:
            engine_obj.post_build(host, version, flatten=flatten, purge_last=purge_last)
        if not save_build_container:
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


def cmdrun_stop(base_path, engine_name, service=[], **kwargs):
    assert_initialized(base_path)
    engine_args = kwargs.copy()
    engine_args.update(locals())
    engine_obj = load_engine(**engine_args)
    with make_temp_dir() as temp_dir:
        hosts = service or (engine_obj.all_hosts_in_orchestration())
        engine_obj.terminate('stop', temp_dir, hosts=hosts)


def cmdrun_restart(base_path, engine_name, service=[], **kwargs):
    assert_initialized(base_path)
    engine_args = kwargs.copy()
    engine_args.update(locals())
    engine_obj = load_engine(**engine_args)
    with make_temp_dir() as temp_dir:
        hosts = service or (engine_obj.all_hosts_in_orchestration())
        engine_obj.restart('restart', temp_dir, hosts=hosts)


def cmdrun_push(base_path, engine_name, username=None, password=None, email=None, push_to=None, tag=None, **kwargs):
    assert_initialized(base_path)
    engine_args = kwargs.copy()
    engine_args.update(locals())
    engine_obj = load_engine(**engine_args)

    # resolve url and namespace
    config = engine_obj.config
    url = engine_obj.default_registry_url
    namespace = None
    if push_to:
        if (config.get('registries') or {}).get(push_to):
            url = config['registries'][push_to].get('url')
            namespace = config['registries'][push_to].get('namespace')
            if not url:
                raise AnsibleContainerRegistryAttributeException("Registry %s missing required attribute 'url'."
                                                                 % push_to)
        else:
            url, namespace = resolve_push_to(push_to, engine_obj.default_registry_url)

    # Check that we can authenticate to the registry and get the username
    username = engine_obj.registry_login(username=username, password=password,
                                         email=email, url=url)
    if not namespace:
        namespace = username

    logger.info('Pushing to "%s/%s' % (re.sub(r'/$', '', url), namespace))

    for host in engine_obj.hosts_touched_by_playbook():
        engine_obj.push_latest_image(host, url=url, namespace=namespace, tag=tag)
    logger.info('Done!')


def cmdrun_shipit(base_path, engine_name, pull_from=None, tag=None, **kwargs):
    assert_initialized(base_path)
    engine_args = kwargs.copy()
    engine_args.update(locals())
    engine_obj = load_engine(**engine_args)
    shipit_engine_name = kwargs.pop('shipit_engine')
    project_name = os.path.basename(base_path).lower()
    local_images = kwargs.get('local_images')

    # determine the registry url and namespace the cluster will use to pull images
    config = engine_obj.config
    url = None
    namespace = None
    if not local_images:
        if not pull_from:
            url = engine_obj.default_registry_url
        elif config.get('registries', {}).get(pull_from):
            url = config['registries'][pull_from].get('url')
            namespace = config['registries'][pull_from].get('namespace')
            if not url:
                raise AnsibleContainerRegistryAttributeException("Registry %s missing required attribute 'url'."
                                                                 % pull_from)
            pull_from = None  # pull_from is now resolved to a url/namespace
        if url and not namespace:
            # try to get the username for the url from the container engine
            try:
                namespace = engine_obj.registry_login(url=url)
            except Exception as exc:
                if "Error while fetching server API version" in str(exc):
                    msg = "Cannot connect to the Docker daemon. Is the daemon running?"
                else:
                    msg = "Unable to determine namespace for registry %s. Error: %s. Either authenticate with the " \
                          "registry or provide a namespace for the registry in container.yml" % (url, str(exc))
                raise AnsibleContainerRegistryAttributeException(msg)

    config = engine_obj.get_config_for_shipit(pull_from=pull_from, url=url, namespace=namespace, tag=tag)

    shipit_engine_obj = load_shipit_engine(AVAILABLE_SHIPIT_ENGINES[shipit_engine_name]['cls'],
                                           config=config,
                                           base_path=base_path,
                                           project_name=project_name)

    # create the role and sample playbook
    shipit_engine_obj.run()
    logger.info('Role %s created.' % project_name)

    if kwargs.get('save_config'):
        # generate and save the configuration templates
        config_path = shipit_engine_obj.save_config()
        logger.info('Saved configuration to %s' % config_path)

def cmdrun_install(base_path, engine_name, roles=[], **kwargs):
    assert_initialized(base_path)
    engine_args = kwargs.copy()
    engine_args.update(locals())
    engine_obj = load_engine(**engine_args)

    with make_temp_dir() as temp_dir:
        engine_obj.orchestrate('install', temp_dir)


def cmdrun_version(base_path, engine_name, debug=False, **kwargs):
    print('Ansible Container, version', __version__)
    if debug:
        print(u', '.join(os.uname()))
        print(sys.version, sys.executable)
        assert_initialized(base_path)
        engine_args = kwargs.copy()
        engine_args.update(locals())
        engine_obj = load_engine(**engine_args)
        engine_obj.print_version_info()

def create_build_container(container_engine_obj, base_path):
    assert_initialized(base_path)
    logger.info('(Re)building the Ansible Container image.')
    build_output = container_engine_obj.build_buildcontainer_image()
    for line in build_output:
        logger.debug(line)
    builder_img_id = container_engine_obj.get_builder_image_id()
    logger.info('Ansible Container image has ID %s', builder_img_id)
    return builder_img_id


def resolve_push_to(push_to, default_url):
    '''
    Given a push-to value, return the registry and namespace.

    :param push_to: string: User supplied --push-to value.
    :param default_index: string: Container engine's default_index value (e.g. docker.io).
    :return: tuple: index_name, namespace
    '''
    protocol = 'http://' if push_to.startswith('http://') else 'https://'
    url = push_to = REMOVE_HTTP.sub('', push_to)
    namespace = None
    parts = url.split('/', 1)
    special_set = {'.', ':'}
    char_set = set([c for c in parts[0]])

    if len(parts) == 1:
        if not special_set.intersection(char_set) and parts[0] != 'localhost':
            registry_url = default_url
            namespace = push_to
        else:
            registry_url = protocol + parts[0]
    else:
        registry_url = protocol + parts[0]
        namespace = parts[1]

    return registry_url, namespace

