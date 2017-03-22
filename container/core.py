# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

from container.common.visibility import getLogger
logger = getLogger(__name__)

import getpass
import gzip
import io
import os
import re
import sys
import tarfile
import time

import requests
from six.moves.urllib.parse import urljoin

from .common.exceptions import AnsibleContainerException, \
    AnsibleContainerAlreadyInitializedException,\
    AnsibleContainerRegistryAttributeException
from .common.utils import *
from .common.loader import load_engine
from . import __version__

REMOVE_HTTP = re.compile('^https?://')
DEFAULT_CONDUCTOR_BASE = 'centos:7'


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
        container_cfg = os.path.join(base_path, 'container.yml')
        if os.path.exists(container_cfg):
            raise AnsibleContainerAlreadyInitializedException()
        if not os.path.exists(base_path):
            os.mkdir(base_path)
        template_dir = os.path.join(jinja_template_path(), 'init')
        context = {
            u'ansible_container_version': __version__,
            u'project_name': kwargs.get('project_name',
                                        os.path.basename(base_path))
        }
        for tmpl_filename in os.listdir(template_dir):
            jinja_render_to_temp(template_dir,
                                 tmpl_filename,
                                 base_path,
                                 tmpl_filename.replace('.j2', ''),
                                 **context)
        logger.info('Ansible Container initialized.')


def cmdrun_build(base_path, project_name, engine_name, var_file=None,
                 **kwargs):
    config = get_config(base_path, var_file=var_file)
    engine_obj = load_engine(['BUILD'],
                             engine_name, project_name or os.path.basename(base_path),
                             config['services'], **kwargs)

    conductor_container_id = engine_obj.get_container_id_for_service('conductor')
    if engine_obj.service_is_running('conductor'):
        engine_obj.stop_container(conductor_container_id, forcefully=True)

    if conductor_container_id is None or not kwargs.get('devel'):
        if engine_obj.CAP_BUILD_CONDUCTOR:
            engine_obj.build_conductor_image(
                base_path,
                (config['settings'] or {}).get('conductor_base', DEFAULT_CONDUCTOR_BASE),
                cache=kwargs['cache']
            )
        else:
            logger.warning(u'%s does not support building the Conductor image.',
                           engine_obj.display_name, engine=engine_obj.display_name)

    if conductor_container_id:
        engine_obj.delete_container(conductor_container_id)

    conductor_container_id = engine_obj.run_conductor('build', dict(config),
                                                      base_path, kwargs)
    try:
        while engine_obj.service_is_running('conductor'):
            time.sleep(0.1)
    finally:
        exit_code = engine_obj.service_exit_code('conductor')
        if not kwargs['save_build_container']:
            logger.info('Conductor terminated. Cleaning up.', save_build_container=False, conductor_id=conductor_container_id)
            if engine_obj.service_is_running('conductor'):
                engine_obj.stop_container(conductor_container_id, forcefully=True)
            engine_obj.delete_container(conductor_container_id)
        else:
            logger.info('Conductor terminated. Preserving as requested.', save_build_container=False, conductor_id=conductor_container_id)
        if exit_code:
            raise AnsibleContainerException(u'Conductor exited with status %s' %
                                            exit_code)


def cmdrun_run(base_path, project_name, engine_name, var_file=None, cache=True,
               **kwargs):
    logger.info('Got extra args to `run` command', arguments=kwargs)
    config = get_config(base_path, var_file=var_file)
    assert_initialized(base_path)

    engine_obj = load_engine(['RUN'],
                             engine_name, project_name or os.path.basename(base_path),
                             config['services'], **kwargs)

    for service in engine_obj.services:
        if not engine_obj.service_is_running(service):
            logger.debug(u'Service not running, will be started by `run`'
                u' command', service=service)
            continue
        logger.info(u'Service is already running, will stopped and'
            u' restarted by `run` command', service=service)
        engine_obj.stop_container(
            engine_obj.get_container_id_for_service(service),
            forcefully=True
        )

    conductor_container_id = engine_obj.run_conductor(
        'run', dict(config), base_path, kwargs)

    try:
        while engine_obj.service_is_running('conductor'):
            time.sleep(0.1)
    finally:
        if not config.get('save_build_container', False):
            logger.info('Conductor terminated. Cleaning up.', save_build_container=False, conductor_id=conductor_container_id)
            if engine_obj.service_is_running('conductor'):
                engine_obj.stop_container(conductor_container_id, forcefully=True)
            engine_obj.delete_container(conductor_container_id)
        else:
            logger.info('Conductor terminated. Preserving as requested.', save_build_container=False, conductor_id=conductor_container_id)


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


def cmdrun_push(base_path, project_name, engine_name, var_file=None, **kwargs):
    """
    Push images to a registry. Requires authenticating with the registry prior to starting
    the push. If your engine's config file does not already contain an authorization for the
    registry, pass username and/or password. If you exclude password, you will be prompted.
    """
    assert_initialized(base_path)
    config = get_config(base_path, var_file=var_file)

    engine_obj = load_engine(['LOGIN', 'PUSH'],
                             engine_name, project_name or os.path.basename(base_path),
                             config['services'], **kwargs)

    config_path = kwargs.get('config_path', engine_obj.auth_config_path)
    username = kwargs.get('username')
    password = kwargs.get('password')
    push_to = kwargs.get('push_to')

    url = engine_obj.default_registry_url
    registry_name = engine_obj.default_registry_name
    namespace = None
    if push_to:
        if config.get('registries', dict()).get(push_to):
            url = config['registries'][push_to].get('url')
            namespace = config['registries'][push_to].get('namespace')
            if not url:
                raise AnsibleContainerRegistryAttributeException(
                    u"Registry {} missing required attribute 'url'".format(push_to)
                )
        else:
            url, namespace = resolve_push_to(push_to, engine_obj.default_registry_url)

    if username and not password:
        # If a username was supplied without a password, prompt for it
        while not password:
            password = getpass.getpass(u"Enter password for {0} at {1}: ".format(username, registry_name))

    if config_path:
        # Make sure the config_path exists
        #  - gives us a chance to create the file with correct permissions, if it does not exists
        #  - makes sure we mount a path to the conductor for a specific file
        config_path = os.path.normpath(os.path.expanduser(config_path))
        if os.path.exists(config_path) and os.path.isdir(config_path):
            raise AnsibleContainerException(
                u"Expecting --config-path to be a path to a file and not a directory"
            )
        elif not os.path.exists(config_path):
            # Make sure the directory path exists
            try:
                os.makedirs(os.path.dirname(config_path), 0o750)
            except OSError:
                raise AnsibleContainerException(
                    u"Failed to create the requested the path {}".format(os.path.dirname(config_path))
                )
            # Touch the file
            open(config_path, 'w').close()

    # If you ran build with --save-build-container, then you're broken without first removing
    #  the old build container.
    remove_existing_container(engine_obj, 'conductor')

    push_params = {}
    push_params.update(kwargs)
    push_params['config_path'] = config_path
    push_params['password'] = password
    push_params['url'] = url
    push_params['namespace'] = namespace

    conductor_container_id = engine_obj.run_conductor('push', dict(config), base_path, push_params)

    try:
        while engine_obj.service_is_running('conductor'):
            time.sleep(0.1)
    finally:
        if not config.get('save_build_container', False):
            logger.info('Conductor terminated. Cleaning up.')
            if engine_obj.service_is_running('conductor'):
                engine_obj.stop_container(conductor_container_id, forcefully=True)
            engine_obj.delete_container(conductor_container_id)
        else:
            logger.info('Conductor terminated. Preserving as requested.')


def cmdrun_shipit(base_path, engine_name, pull_from=None, **kwargs):
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

    config = engine_obj.get_config_for_shipit(pull_from=pull_from, url=url, namespace=namespace)

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


def cmdrun_import(base_path, project_name, engine_name, **kwargs):
    engine_obj = load_engine(['IMPORT'],
                             engine_name,
                             project_name or os.path.basename(base_path),
                             {}, **kwargs)

    engine_obj.import_project(base_path, **kwargs)
    logger.info('Project imported.')


def remove_existing_container(engine_obj, service_name):
    """
    Remove a container for an existing service. Handy for removing an existing conductor.
    """
    conductor_container_id = engine_obj.get_container_id_for_service(service_name)
    if engine_obj.service_is_running(service_name):
        engine_obj.stop_container(conductor_container_id, forcefully=True)
    if conductor_container_id:
        engine_obj.delete_container(conductor_container_id)


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
    :param default_url: string: Container engine's default_index value (e.g. docker.io).
    :return: tuple: registry_url, namespace
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

