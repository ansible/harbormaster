# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

from .utils.visibility import getLogger
logger = getLogger(__name__)

import logging
plainLogger = logging.getLogger(__name__)

import getpass
import gzip
import hashlib
import io
import os
import re
import ruamel
import shutil
import sys
import subprocess
import tarfile
import time
import tempfile

try:
    from shlex import quote
except ImportError:
    from pipes import quote

import requests

from six import iteritems
from six.moves.urllib.parse import urljoin

from .exceptions import AnsibleContainerAlreadyInitializedException,\
                        AnsibleContainerRegistryAttributeException, \
                        AnsibleContainerException, \
                        AnsibleContainerConfigException
from .utils import *
from .utils import resolve_config_path
from . import __version__, host_only, conductor_only, ENV
from .config import DEFAULT_CONDUCTOR_BASE
from container.utils.loader import load_engine

if ENV == 'conductor':
    from container.utils.galaxy import AnsibleContainerGalaxy


REMOVE_HTTP = re.compile('^https?://')


@host_only
def hostcmd_init(base_path, project=None, force=False, config_file=None, **kwargs):
    container_cfg = resolve_config_path(base_path, config_file)
    if os.path.exists(container_cfg) and not force:
        raise AnsibleContainerAlreadyInitializedException()

    if project:
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
        template_dir = os.path.join(jinja_template_path(), 'init')
        context = {
            u'ansible_container_version': __version__,
            u'project_name': kwargs.get('project_name') or
                                        os.path.basename(base_path),
            u'default_base': DEFAULT_CONDUCTOR_BASE
        }
        for tmpl_filename in os.listdir(template_dir):
            jinja_render_to_temp(template_dir,
                                 tmpl_filename,
                                 base_path,
                                 tmpl_filename.replace('.j2', ''),
                                 **context)
        logger.info('Ansible Container initialized.')

@host_only
def hostcmd_prebake(distros, debug=False, cache=True, ignore_errors=False):
    logger.info('Prebaking distros...', distros=distros, cache=cache)
    engine_obj = load_engine(['BUILD_CONDUCTOR'], 'docker', os.getcwd(), {}, debug=debug)
    from .docker.engine import PREBAKED_DISTROS
    for distro in (distros or PREBAKED_DISTROS):
        logger.info('Now prebaking Conductor image for %s', distro)
        try:
            engine_obj.build_conductor_image(os.getcwd(),
                                             distro,
                                             prebaking=True,
                                             cache=cache)
        except Exception as e:
            logger.exception('Failure building prebaked image for %s', distro)
            if ignore_errors:
                continue
        except KeyboardInterrupt:
            if ignore_errors:
                continue


@host_only
def hostcmd_build(base_path, project_name, engine_name, vars_files=None, config_file=None, **kwargs):
    conductor_cache = kwargs['cache'] and kwargs['conductor_cache']
    assert_initialized(base_path, config_file)
    config = get_config(base_path, vars_files=vars_files, engine_name=engine_name, project_name=project_name,
                        config_file=config_file)
    requested_services = kwargs.get('services_to_build')
    config.check_requested_services(requested_services)

    engine_obj = load_engine(['BUILD', 'RUN'],
                             engine_name, config.project_name,
                             config['services'], **kwargs)

    conductor_container_id = engine_obj.get_container_id_for_service('conductor')
    conductor_image_id = engine_obj.get_latest_image_id_for_service('conductor')
    if engine_obj.service_is_running('conductor'):
        engine_obj.stop_container(conductor_container_id, forcefully=True)

    if conductor_image_id is None or not kwargs.get('devel'):
        #TODO once we get a conductor running, figure out how to know it's running
        if engine_obj.CAP_BUILD_CONDUCTOR:
            env_vars = []
            if config.get('settings', {}).get('conductor', {}).get('environment', {}):
                environment = config['settings']['conductor']['environment']
                if isinstance(environment, dict):
                    for key, value in iteritems(environment):
                        env_vars.append('{}={}'.format(key, value))
                else:
                    env_vars = environment
            if kwargs.get('with_variables'):
                env_vars += kwargs['with_variables']

            engine_obj.build_conductor_image(
                base_path,
                config.conductor_base,
                cache=conductor_cache,
                environment=env_vars
            )
        else:
            logger.warning(u'%s does not support building the Conductor image.',
                           engine_obj.display_name, engine=engine_obj.display_name)

    if conductor_container_id:
        engine_obj.delete_container(conductor_container_id)

    logger.debug('Config settings', config=config, rawsettings=config.get('settings'),
                 conf=type(config), settings=config.get('settings', {}))

    save_container = config.save_conductor
    if kwargs.get('save_conductor_container'):
        # give precedence to CLI option
        save_container = True

    kwargs['cache'] = kwargs['cache'] and kwargs['container_cache']
    kwargs['config_vars'] = config.get('defaults')
    engine_obj.await_conductor_command(
        'build', dict(config), base_path, kwargs, save_container=save_container)

@host_only
def hostcmd_deploy(base_path, project_name, engine_name, vars_files=None, cache=True, vault_files=None,
                   config_file=None, **kwargs):
    assert_initialized(base_path, config_file)
    config = get_config(base_path, vars_files=vars_files, engine_name=engine_name, project_name=project_name,
                        vault_files=vault_files, config_file=config_file)
    local_images = kwargs.get('local_images')
    output_path = kwargs.pop('deployment_output_path', None) or config.deployment_path

    engine_obj = load_engine(['LOGIN', 'PUSH', 'DEPLOY'],
                             engine_name, config.project_name,
                             config['services'], **kwargs)

    params = {
        'deployment_output_path': os.path.normpath(os.path.abspath(os.path.expanduser(output_path))),
        'host_user_uid': os.getuid(),
        'host_user_gid': os.getgid(),
        'settings': config.get('settings', {}),
    }
    if kwargs:
        params.update(kwargs)

    if not local_images:
        push_options = push_images(base_path, config.image_namespace, engine_obj, config,
                                   save_conductor=False, **params)
        params.update(push_options)

    params['vault_files'] = config.vault_files

    engine_obj.await_conductor_command(
        'deploy', dict(config), base_path, params, save_container=config.save_conductor)

@host_only
def hostcmd_run(base_path, project_name, engine_name, vars_files=None, cache=True, ask_vault_pass=False,
                config_file=None, **kwargs):
    assert_initialized(base_path, config_file)
    logger.debug('Got extra args to `run` command', arguments=kwargs)
    config = get_config(base_path, vars_files=vars_files, engine_name=engine_name, project_name=project_name,
                        config_file=config_file)
    if not kwargs['production']:
        config.set_env('dev')

    services = kwargs.pop('service')
    config.check_requested_services(services)
    config.set_services(services)
    conductor_env = config.get_conductor_environment() 
    config.set_conductor_environment(conductor_env)

    logger.debug('hostcmd_run configuration', config=config.__dict__)

    engine_obj = load_engine(['RUN'],
                             engine_name, config.project_name,
                             config['services'], **kwargs)

    remove_existing_container(engine_obj, 'conductor', remove_volumes=True)

    params = {
        'deployment_output_path': config.deployment_path,
        'host_user_uid': os.getuid(),
        'host_user_gid': os.getgid(),
        'settings': config.get('settings', {}), 
    }
    if kwargs:
        params.update(kwargs)

    logger.debug('Params passed to conductor for run', params=params)

    if ask_vault_pass:
        params['vault_password'] = getpass.getpass(u"Enter the vault password: ")

    engine_obj.await_conductor_command(
        'run', dict(config), base_path, params, save_container=config.save_conductor)

@host_only
def hostcmd_destroy(base_path, project_name, engine_name, vars_files=None, cache=True, config_file=None, **kwargs):
    assert_initialized(base_path, config_file)
    logger.debug('Got extra args to `destroy` command', arguments=kwargs)
    config = get_config(base_path, vars_files=vars_files, engine_name=engine_name, project_name=project_name,
                        config_file=config_file)
    if not kwargs['production']:
        config.set_env('dev')

    engine_obj = load_engine(['RUN'],
                             engine_name, config.project_name,
                             config['services'], **kwargs)

    remove_existing_container(engine_obj, 'conductor', remove_volumes=True)

    params = {
        'deployment_output_path': config.deployment_path,
        'host_user_uid': os.getuid(),
        'host_user_gid': os.getgid(),
        'settings': config.get('settings', {})
    }
    if kwargs:
        params.update(kwargs)

    engine_obj.await_conductor_command(
        'destroy', dict(config), base_path, params, save_container=config.save_conductor)

@host_only
def hostcmd_stop(base_path, project_name, engine_name, vars_files=None, force=False, services=[], config_file=None,
                 **kwargs):
    assert_initialized(base_path, config_file)
    config = get_config(base_path, vars_files=vars_files, engine_name=engine_name, project_name=project_name,
                        config_file=config_file)
    if not kwargs['production']:
        config.set_env('dev')

    services = kwargs.pop('service')
    config.check_requested_services(services)
    config.set_services(services)

    engine_obj = load_engine(['RUN'],
                             engine_name, config.project_name,
                             config['services'], **kwargs)

    params = {
        'deployment_output_path': config.deployment_path,
        'host_user_uid': os.getuid(),
        'host_user_gid': os.getgid(),
        'settings': config.get('settings', {})
    }
    if kwargs:
        params.update(kwargs)

    engine_obj.await_conductor_command(
        'stop', dict(config), base_path, params, save_container=config.save_conductor)


@host_only
def hostcmd_restart(base_path, project_name, engine_name, vars_files=None, force=False, services=[], config_file=None,
                    **kwargs):
    assert_initialized(base_path, config_file)
    config = get_config(base_path, vars_files=vars_files, engine_name=engine_name,  project_name=project_name,
                        config_file=config_file)
    if not kwargs['production']:
        config.set_env('dev')

    services = kwargs.pop('service')
    config.check_requested_services(services)
    config.set_services(services)
    conductor_env = config.get_conductor_environment()
    config.set_conductor_environment(conductor_env)

    engine_obj = load_engine(['RUN'],
                             engine_name, config.project_name,
                             config['services'], **kwargs)
    params = {
        'deployment_output_path': config.deployment_path,
        'host_user_uid': os.getuid(),
        'host_user_gid': os.getgid(),
        'settings': config.get('settings', {})
    }
    if kwargs:
        params.update(kwargs)

    engine_obj.await_conductor_command(
        'restart', dict(config), base_path, params, save_container=config.save_conductor)


@host_only
def hostcmd_push(base_path, project_name, engine_name, vars_files=None, config_file=None, **kwargs):
    """
    Push images to a registry. Requires authenticating with the registry prior to starting
    the push. If your engine's config file does not already contain an authorization for the
    registry, pass username and/or password. If you exclude password, you will be prompted.
    """
    assert_initialized(base_path, config_file)
    config = get_config(base_path, vars_files=vars_files, engine_name=engine_name, project_name=project_name,
                        config_file=config_file)

    engine_obj = load_engine(['LOGIN', 'PUSH'],
                             engine_name, config.project_name,
                             config['services'], **kwargs)
    logger.debug('PROJECT NAME', project_name=config.project_name)
    push_images(base_path,
                config.image_namespace,
                engine_obj,
                config,
                save_conductor=config.save_conductor,
                **kwargs)


@host_only
def push_images(base_path, image_namespace, engine_obj, config, **kwargs):
    """ Pushes images to a Docker registry. Returns dict containing attributes used to push images. """
    config_path = kwargs.get('config_path', engine_obj.auth_config_path)
    username = kwargs.get('username')
    password = kwargs.get('password')
    push_to = kwargs.get('push_to')
    url = engine_obj.default_registry_url
    registry_name = engine_obj.default_registry_name
    namespace = image_namespace
    save_conductor = config.save_conductor
    repository_prefix = None
    pull_from_url = None

    if push_to:
        if config.get('registries', dict()).get(push_to):
            url = config['registries'][push_to].get('url')
            namespace = config['registries'][push_to].get('namespace', namespace)
            repository_prefix = config['registries'][push_to].get('repository_prefix')
            pull_from_url = config['registries'][push_to].get('pull_from_url')
            if not url:
                raise AnsibleContainerRegistryAttributeException(
                    u"Registry {} missing required attribute 'url'".format(push_to)
                )
        else:
            url, namespace = resolve_push_to(push_to, engine_obj.default_registry_url, namespace)

    if username and not password:
        # If a username was supplied without a password, prompt for it
        if url != engine_obj.default_registry_url:
            registry_name = url
        while not password:
            password = getpass.getpass(u"Enter password for {0} at {1}: ".format(username, registry_name))

    if config_path:
        # Make sure the config_path exists
        #  - gives us a chance to create the file with correct permissions, if it does not exists
        #  - makes sure we mount a path to the conductor for a specific file
        config_path = os.path.normpath(os.path.expanduser(config_path))
        if os.path.exists(config_path) and os.path.isdir(config_path):
            raise AnsibleContainerException(
                u"Expecting --config-path to be a path to a file, not a directory"
            )
        elif not os.path.exists(config_path):
            # Make sure the directory path exists
            if not os.path.exists(os.path.dirname(config_path)):
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
    remove_existing_container(engine_obj, 'conductor', remove_volumes=True)

    push_params = {}
    push_params.update(kwargs)
    push_params['config_path'] = config_path
    push_params['password'] = password
    push_params['url'] = url
    push_params['namespace'] = namespace
    push_params['repository_prefix'] = repository_prefix
    push_params['pull_from_url'] = pull_from_url

    # Push
    engine_obj.await_conductor_command('push', dict(config), base_path, push_params, save_container=save_conductor)

    return {'url': url,
            'namespace': namespace,
            'repository_prefix': repository_prefix,
            'pull_from_url': pull_from_url }


@host_only
def hostcmd_install(base_path, project_name, engine_name, config_file=None, **kwargs):
    assert_initialized(base_path, config_file)
    config = get_config(base_path, engine_name=engine_name, project_name=project_name, config_file=config_file)
    save_conductor = config.save_conductor
    engine_obj = load_engine(['INSTALL'],
                             engine_name, config.project_name,
                             config['services'], **kwargs)
    engine_obj.await_conductor_command('install',
                                       dict(config),
                                       base_path,
                                       kwargs,
                                       save_container=save_conductor)

@host_only
def hostcmd_version(base_path, project_name, engine_name, config_file=None, **kwargs):
    print('Ansible Container, version', __version__)
    if kwargs.get('debug', False):
        print(u', '.join(os.uname()))
        print(sys.version, sys.executable)
        assert_initialized(base_path, config_file)
        engine_obj = load_engine(['VERSION'],
                                 engine_name,
                                 project_name or os.path.basename(base_path),
                                 {}, **kwargs)
        engine_obj.print_version_info()


@host_only
def hostcmd_import(base_path, project_name, engine_name, config_file=None, **kwargs):
    engine_obj = load_engine(['IMPORT'],
                             engine_name,
                             project_name or os.path.basename(base_path),
                             {}, **kwargs)

    engine_obj.import_project(base_path, **kwargs)
    logger.info('Project imported.')


@host_only
def remove_existing_container(engine_obj, service_name, remove_volumes=False):
    """
    Remove a container for an existing service. Handy for removing an existing conductor.
    """
    conductor_container_id = engine_obj.get_container_id_for_service(service_name)
    if engine_obj.service_is_running(service_name):
        engine_obj.stop_container(conductor_container_id, forcefully=True)
    if conductor_container_id:
        engine_obj.delete_container(conductor_container_id, remove_volumes=remove_volumes)


@host_only
def resolve_push_to(push_to, default_url, default_namespace):
    '''
    Given a push-to value, return the registry and namespace.

    :param push_to: string: User supplied --push-to value.
    :param default_url: string: Container engine's default_index value (e.g. docker.io).
    :return: tuple: registry_url, namespace
    '''
    protocol = 'http://' if push_to.startswith('http://') else 'https://'
    url = push_to = REMOVE_HTTP.sub('', push_to)
    namespace = default_namespace
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


@conductor_only
def set_path_ownership(path, uid, gid):
    """
    Starting with the path, recursively set ownership of files and subdirectories.
    :param path: Root path
    :param uid: User ID
    :param gid: Group ID
    :return: None
    """
    os.chown(path, uid, gid)
    for root, dirs, files in os.walk(path):
        for d in dirs:
            os.chown(os.path.join(root, d), uid, gid)
        for f in files:
            os.chown(os.path.join(root, f), uid, gid)


@conductor_only
def run_playbook(playbook, engine, service_map, ansible_options='', local_python=False, debug=False,
                 deployment_output_path=None, tags=None, build=False, vault_password=None,
                 vault_password_file=None, **kwargs):
    uid, gid = kwargs.get('host_user_uid', 1), kwargs.get('host_user_gid', 1)
    return_code = 0
    try:
        if deployment_output_path:
            remove_tmpdir = False
            output_dir = deployment_output_path
        else:
            remove_tmpdir = True
            output_dir = tempfile.mkdtemp()

        playbook_path = os.path.join(output_dir, 'playbook.yml')
        logger.debug("writing playbook to {}".format(playbook_path))
        logger.debug("playbook", playbook=playbook)
        with open(playbook_path, 'w') as ofs:
            ofs.write(ruamel.yaml.round_trip_dump(playbook, indent=4, block_seq_indent=2, default_flow_style=False))

        inventory_path = os.path.join(output_dir, 'hosts')
        with open(inventory_path, 'w') as ofs:
            for service_name, container_id in service_map.items():
                if not local_python:
                    # Use Python runtime from conductor
                    ofs.write('%s ansible_host="%s" ansible_python_interpreter="%s"\n' % (
                        service_name, container_id, engine.python_interpreter_path))
                else:
                    # Use local Python runtime
                    ofs.write('%s ansible_host="%s"\n' % (service_name, container_id))

        if not os.path.exists(os.path.join(output_dir, 'files')):
            os.mkdir(os.path.join(output_dir, 'files'))
        if not os.path.exists(os.path.join(output_dir, 'templates')):
            os.mkdir(os.path.join(output_dir, 'templates'))

        set_path_ownership(output_dir, uid, gid)

        rc = subprocess.call(['mount', '--bind', '/src',
                              os.path.join(output_dir, 'files')])
        if rc:
            raise OSError('Could not bind-mount /src into tmpdir')
        rc = subprocess.call(['mount', '--bind', '/src',
                              os.path.join(output_dir, 'templates')])
        if rc:
            raise OSError('Could not bind-mount /src into tmpdir')

        if vault_password_file:
            vault_password_file = '--vault-password-file {}'.format(vault_password_file)
        elif vault_password:
            # User entered password
            vault_pass_path = os.path.join(output_dir, '.vault-pass.txt')
            with open(vault_pass_path, 'w') as ofs:
                ofs.write(vault_password)
            vault_password_file = '--vault-password-file {}'.format(vault_pass_path)

        ansible_args = dict(inventory=quote(inventory_path),
                            playbook=quote(playbook_path),
                            debug_maybe='-vvvv' if debug else '',
                            build_args=engine.ansible_build_args if build else '',
                            orchestrate_args=engine.ansible_orchestrate_args if not build else '',
                            ansible_playbook=engine.ansible_exec_path,
                            ansible_options=' '.join(ansible_options) or '',
                            vault_password_file=vault_password_file if vault_password_file else '')

        if tags:
            ansible_args['ansible_options'] += ' --tags={} '.format(','.join(tags))
        else:
            pass

        # env = os.environ.copy()
        # env['ANSIBLE_REMOTE_TEMP'] = '/tmp/.ansible-${USER}/tmp'

        env = {}
        env.update(os.environ)

        ansible_cmd = ('{ansible_playbook} '
                       '{debug_maybe} '
                       '{ansible_options} '
                       '-i {inventory} '
                       '{build_args} '
                       '{orchestrate_args} '
                       '{playbook} '
                       '{vault_password_file}').format(**ansible_args)

        logger.debug('Running Ansible Playbook', command=ansible_cmd, cwd='/src')
        process = subprocess.Popen(ansible_cmd,
                                   shell=True,
                                   bufsize=1,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   cwd='/src',
                                   env=env
                                   )

        log_iter = iter(process.stdout.readline, '')
        while process.returncode is None:
            try:
                plainLogger.info(log_iter.next().rstrip())
            except StopIteration:
                process.wait()
            finally:
                process.poll()

        return_code = process.returncode
    finally:
        try:
            rc = subprocess.call(['unmount',
                                  os.path.join(output_dir, 'files')])
            rc = subprocess.call(['unmount',
                                  os.path.join(output_dir, 'templates')])
        except Exception:
            pass
        try:
            if remove_tmpdir:
                shutil.rmtree(output_dir, ignore_errors=True)
        except Exception:
            pass

    return return_code

@conductor_only
def apply_role_to_container(role, container_id, service_name, engine, vars={},
                            local_python=False, ansible_options='',
                            debug=False):
    playbook = [
        {'hosts': service_name,
         'vars': vars,
         'roles': [role],
         }
    ]

    if isinstance(role, dict) and 'gather_facts' in role:
        # Allow disabling gather_facts at the role level
        playbook[0]['gather_facts'] = role.pop('gather_facts')

    container_metadata = engine.inspect_container(container_id)
    onbuild = container_metadata['Config']['OnBuild']
    # FIXME: Actually do stuff if onbuild is not null

    rc = run_playbook(playbook, engine, {service_name: container_id}, ansible_options=ansible_options,
                      local_python=local_python, debug=debug, build=True)
    if rc:
        logger.error('Error applying role!', playbook=playbook, engine=engine,
            exit_code=rc)
    return rc


@conductor_only
def conductorcmd_build(engine_name, project_name, services, cache=True, local_python=False,
                       ansible_options='', debug=False, config_vars=None, **kwargs):
    engine = load_engine(['BUILD'], engine_name, project_name, services, **kwargs)
    logger.info(u'%s integration engine loaded. Build starting.', engine.display_name, project=project_name)
    services_to_build = kwargs.get('services_to_build') or services.keys()
    logger.debug("Services to build", services_to_build=services_to_build)
    for service_name, service in services.items():
        if service_name not in services_to_build:
            logger.debug('Skipping service %s...', service_name)
            continue
        logger.info(u'Building service...', service=service_name, project=project_name)
        if not service.get('from'):
            raise AnsibleContainerConfigException(
                "Expecting service to have 'from' attribute. None found when evaluating "
                "service: {}.".format(service_name)
            )
        cur_image_id = engine.get_image_id_by_tag(service['from'])
        if not cur_image_id:
            cur_image_id = engine.pull_image_by_tag(service['from'])
            if not cur_image_id:
                raise AnsibleContainerException(
                    "Failed to find image {}. Try `docker image pull {}`".format(service['from'])
                )
        # the fingerprint hash tracks cacheability
        fingerprint_hash = hashlib.sha256('%s::' % cur_image_id)
        logger.debug(u'Base fingerprint hash = %s', fingerprint_hash.hexdigest(),
                     service=service_name, hash=fingerprint_hash.hexdigest())
        cache_busted = not cache

        cur_container_id = engine.get_container_id_for_service(service_name)
        if cur_container_id:
            if engine.service_is_running(service_name):
                engine.stop_container(cur_container_id, forcefully=True)
            engine.delete_container(cur_container_id)

        if service.get('roles'):
            for role in service['roles']:
                role_fingerprint = get_role_fingerprint(role)
                fingerprint_hash.update(role_fingerprint)

                if not cache_busted:
                    logger.debug(u'Still trying to keep cache.', service=service_name)
                    cached_image_id = engine.get_image_id_by_fingerprint(
                        fingerprint_hash.hexdigest())
                    if cached_image_id:
                        # We can reuse the cached image
                        logger.debug(u'Cached layer found for service',
                                     service=service_name, fingerprint=fingerprint_hash.hexdigest())
                        cur_image_id = cached_image_id
                        logger.info(u'Applied role %s from cache', role,
                                    service=service_name, role=role)
                        continue
                    else:
                        cache_busted = True
                        logger.debug(u'Cache busted! No layer found',
                            service=service_name,
                            fingerprint=fingerprint_hash.hexdigest(),
                        )
                run_kwargs = dict(
                    name=engine.container_name_for_service(service_name),
                    user='root',
                    working_dir='/',
                    command='sh -c "while true; do sleep 1; '
                            'done"',
                    entrypoint=[],
                    privileged=True,
                    volumes=dict(),
                    environment=dict(ANSIBLE_CONTAINER=1)
                )

                if service.get('build_overrides'):
                    for key in service['build_overrides']:
                        if key in ['user', 'working_dir', 'command', 'privileged']:
                            run_kwargs[key] = service['build_overrides'][key]

                    run_kwargs['environment'].update(service['build_overrides']['environment'])

                if service.get('volumes'):
                    for volume in service['volumes']:
                        pieces = volume.split(':')
                        src = pieces[0]
                        bind = pieces[0]
                        mode = 'rw'
                        if len(pieces) > 1:
                            bind = pieces[1]
                        if len(pieces) > 2:
                            mode = pieces[2]
                        run_kwargs[u'volumes'][src] = {u'bind': bind, u'mode': mode}

                if not local_python:
                    # If we're on a debian based distro, we need the correct architecture
                    # to allow python to load dynamically loaded shared libraries
                    extra_library_paths = ''
                    try:
                        architecture = subprocess.check_output(['dpkg-architecture',
                                                                   '-qDEB_HOST_MULTIARCH'])
                        architecture = architecture.strip()
                        logger.debug(u'Detected architecture %s', architecture,
                                       service=service_name, architecture=architecture)
                        extra_library_paths = (':/_usr/lib/{0}:/_usr/local/lib/{0}'
                                               ':/_lib/{0}').format(architecture)
                    except Exception:
                        # we're not on debian/ubuntu or a system without multiarch support
                        pass

                    # Use the conductor's Python runtime
                    run_kwargs['volumes'][engine.get_runtime_volume_id('/usr')] = {'bind': '/_usr', 'mode': 'ro'}
                    try:
                        run_kwargs['volumes'][engine.get_runtime_volume_id('/lib')] = {'bind': '/_lib', 'mode': 'ro'}
                        extra_library_paths += ":/_lib"
                    except ValueError:
                        # No /lib volume
                        pass
                    run_kwargs['environment'].update(dict(
                         LD_LIBRARY_PATH='/usr/lib:/usr/lib64:/_usr/lib:/_usr/lib64:/_usr/local/lib{}'.format(extra_library_paths),
                         CPATH='/usr/include:/usr/local/include:/_usr/include:/_usr/local/include',
                         PATH='/usr/local/sbin:/usr/local/bin:'
                              '/usr/sbin:/usr/bin:/sbin:/bin:'
                              '/_usr/sbin:/_usr/bin:'
                              '/_usr/local/sbin:/_usr/local/bin',
                         # PYTHONPATH='/_usr/lib/python2.7'
                    ))

                container_id = engine.run_container(cur_image_id, service_name, **run_kwargs)

                while not engine.service_is_running(service_name):
                    time.sleep(0.2)
                logger.debug('Container running', id=container_id)

                rc = apply_role_to_container(role, container_id, service_name,
                                             engine, vars=config_vars,
                                             local_python=local_python,
                                             ansible_options=ansible_options,
                                             debug=debug)
                logger.debug('Playbook run finished.', exit_code=rc)
                if rc:
                    raise RuntimeError('Build failed.')
                logger.info(u'Applied role to service', service=service_name, role=role)

                engine.stop_container(container_id, forcefully=True)
                is_last_role = role is service['roles'][-1]
                if is_last_role and kwargs.get('flatten'):
                    logger.debug("Finished build, flattening image")
                    image_id = engine.flatten_container(container_id, service_name, service)
                    logger.info(u'Saved flattened image for service', service=service_name, image=image_id)
                else:
                    image_id = engine.commit_role_as_layer(container_id,
                                                           service_name,
                                                           fingerprint_hash.hexdigest(),
                                                           service,
                                                           with_name=is_last_role)
                    logger.info(u'Committed layer as image', service=service_name, image=image_id)
                engine.delete_container(container_id)
                cur_image_id = image_id
            # Tag the image also as latest:
            engine.tag_image_as_latest(service_name, cur_image_id)
            logger.info(u'Build complete.', service=service_name)
        else:
            logger.info(u'Service had no roles specified. Nothing to do.', service=service_name)
    logger.info(u'All images successfully built.')


@conductor_only
def conductorcmd_run(engine_name, project_name, services, **kwargs):
    engine = load_engine(['RUN'], engine_name, project_name, services, **kwargs)

    logger.info(u'Engine integration loaded. Preparing run.',
                engine=engine.display_name)

    engine.containers_built_for_services(
        [service for service, service_desc in services.items()
         if service_desc.get('roles')])

    playbook = engine.generate_orchestration_playbook(**kwargs)
    rc = run_playbook(playbook, engine, services, tags=['start'], **kwargs)
    if rc:
        raise AnsibleContainerException(
            'Error executing the run command. Not all containers may be running.'
        )
    logger.info(u'All services running.', playbook_rc=rc)


@conductor_only
def conductorcmd_restart(engine_name, project_name, services, **kwargs):
    engine = load_engine(['RUN'], engine_name, project_name, services, **kwargs)
    logger.info(u'Engine integration loaded. Preparing to restart containers.',
                engine=engine.display_name)
    playbook = engine.generate_orchestration_playbook(**kwargs)
    rc = run_playbook(playbook, engine, services, tags=['restart'], **kwargs)
    if rc:
        raise AnsibleContainerException(
            'Error executing the restart command. Not all containers may be running.'
        )
    logger.info(u'All services restarted.', playbook_rc=rc)


@conductor_only
def conductorcmd_stop(engine_name, project_name, services, **kwargs):
    engine = load_engine(['RUN'], engine_name, project_name, services, **kwargs)
    logger.info(u'Engine integration loaded. Preparing to stop all containers.',
                engine=engine.display_name)
    playbook = engine.generate_orchestration_playbook(**kwargs)
    rc = run_playbook(playbook, engine, services, tags=['stop'], **kwargs)
    if rc:
        raise AnsibleContainerException(
            "Error executing the stop command. Some containers may still be running."
        )
    logger.info(u'All services stopped.', playbook_rc=rc)


@conductor_only
def conductorcmd_destroy(engine_name, project_name, services, **kwargs):
    engine = load_engine(['RUN'], engine_name, project_name, services, **kwargs)
    logger.info(u'Engine integration loaded. Preparing to stop+delete all '
                u'containers and built images.',
                engine=engine.display_name)
    playbook = engine.generate_orchestration_playbook(**kwargs)
    rc = run_playbook(playbook, engine, services, tags=['destroy'], **kwargs)
    if rc:
        raise AnsibleContainerException(
            'Error executing the destroy command. Not all containers and images may have been removed.'
        )
    logger.info(u'All services destroyed.', playbook_rc=rc)

@conductor_only
def conductorcmd_deploy(engine_name, project_name, services, **kwargs):
    uid, gid = kwargs.get('host_user_uid', 1), kwargs.get('host_user_gid', 1)

    engine = load_engine(['DEPLOY'], engine_name, project_name, services, **kwargs)
    logger.info(u'Engine integration loaded. Preparing deploy.',
                engine=engine.display_name)

    # Verify all images are built
    for service_name, service_defn in services.items():
        if service_defn.get('roles'):
            logger.info(u'Verifying image for %s', service_name)
            image_id = engine.get_latest_image_id_for_service(service_name)
            if not image_id:
                msg = u'Missing image for {}. Run "ansible-container build" to (re)create it.'.format(service_name)
                logger.error(msg, service=service_name)
                raise RuntimeError(msg)

    deployment_output_path = kwargs.get('deployment_output_path')
    playbook = engine.generate_orchestration_playbook(**kwargs)

    engine.pre_deployment_setup(project_name, services, **kwargs)

    try:
        with open(os.path.join(deployment_output_path, '%s.yml' % project_name), 'w') as ofs:
            ofs.write(ruamel.yaml.round_trip_dump(playbook, indent=4, block_seq_indent=2, default_flow_style=False))

    except OSError:
        logger.error(u'Failure writing deployment playbook', exc_info=True)
        raise

    set_path_ownership(deployment_output_path, uid, gid)

@conductor_only
def conductorcmd_install(engine_name, project_name, services, **kwargs):
    roles = kwargs.pop('roles', None)
    logger.debug("Installing roles", roles=roles)
    if roles:
        galaxy = AnsibleContainerGalaxy()
        galaxy.install(roles)

@conductor_only
def conductorcmd_push(engine_name, project_name, services, **kwargs):
    """ Push images to a registry """
    username = kwargs.pop('username')
    password = kwargs.pop('password')
    email = kwargs.pop('email')
    url = kwargs.pop('url')
    namespace = kwargs.pop('namespace')
    tag = kwargs.pop('tag')
    config_path = kwargs.pop('config_path')
    repository_prefix =kwargs.pop('repository_prefix')

    engine = load_engine(['PUSH', 'LOGIN'], engine_name, project_name, services)
    logger.info(u'Engine integration loaded. Preparing push.',
                engine=engine.display_name)

    # Verify that we can authenticate with the registry
    username, password = engine.login(username, password, email, url, config_path)

    # Push each image that has been built using Ansible roles
    for name, service in iteritems(services):
        if service.get('containers'):
            for c in service['containers']:
                if 'roles' in c:
                    cname = '%s-%s' % (name, c['container_name'])
                    image_id = engine.get_latest_image_id_for_service(cname)
                    engine.push(image_id, cname, url=url, tag=tag, namespace=namespace, username=username,
                                password=password, repository_prefix=repository_prefix)
        elif 'roles' in service:
            # if the service has roles, it's an image we should push
            image_id = engine.get_latest_image_id_for_service(name)
            engine.push(image_id, name, url=url, tag=tag, namespace=namespace, username=username,
                        password=password, repository_prefix=repository_prefix)
