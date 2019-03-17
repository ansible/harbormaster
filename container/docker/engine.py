# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
plainLogger = logging.getLogger(__name__)

from container.utils.visibility import getLogger
logger = getLogger(__name__)

import base64
import datetime
import functools
import time
import inspect
import json
import os
import re
import shutil
import sys
import tarfile

from ruamel.yaml.comments import CommentedMap
from six import reraise, iteritems, string_types, PY3

if PY3:
    from functools import reduce
try:
    import httplib as StatusCodes
except ImportError:
    from http import HTTPStatus as StatusCodes

import container
from container import host_only, conductor_only
from container.engine import BaseEngine
from container import utils, exceptions
from container.utils import (logmux, text, ordereddict_to_list, roles_to_install, modules_to_install,
                             ansible_config_exists, create_file)
from .secrets import DockerSecretsMixin

try:
    import docker
    from docker import errors as docker_errors
    from docker.utils.ports import build_port_bindings
    from docker.errors import DockerException
    from docker.api.container import ContainerApiMixin
    from docker.models.containers import RUN_HOST_CONFIG_KWARGS
    from docker.constants import DEFAULT_TIMEOUT_SECONDS
except ImportError:
    raise ImportError(
        u'You must install Ansible Container with Docker(tm) support. '
        u'Try:\npip install ansible-container[docker]==%s' % (
        container.__version__
    ))

TEMPLATES_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        'templates'))

FILES_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        'files'))

DOCKER_VERSION = '17.04.0-ce'

DOCKER_DEFAULT_CONFIG_PATH = os.path.join(os.environ.get('HOME', ''), '.docker', 'config.json')

DOCKER_CONFIG_FILEPATH_CASCADE = [
    os.environ.get('DOCKER_CONFIG', ''),
    DOCKER_DEFAULT_CONFIG_PATH,
    os.path.join(os.environ.get('HOME', ''), '.dockercfg')
]

REMOVE_HTTP = re.compile('^https?://')

# A map of distros and their aliases that we build pre-baked builders for
PREBAKED_DISTROS = {
    'centos:7': ['centos:latest', 'centos:centos7'],
    'fedora:27': ['fedora:latest'],
    'fedora:26': [],
    'fedora:25': [],
    #'amazonlinux:2': ['amazonlinux:2'],
    'debian:jessie': ['debian:8', 'debian:latest', 'debian:jessie-slim'],
    'debian:stretch': ['debian:9', 'debian:stretch-slim'],
    'debian:wheezy': ['debian:7', 'debian:wheezy-slim'],
    'ubuntu:precise': ['ubuntu:12.04'],
    'ubuntu:trusty': ['ubuntu:14.04'],
    'ubuntu:xenial': ['ubuntu:16.04'],
    # 'ubuntu:zesty': ['ubuntu:17.04'],
    'alpine:3.5': ['alpine:latest'],
    'alpine:3.4': []
}

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

def get_timeout():
    timeout = DEFAULT_TIMEOUT_SECONDS
    source = None
    if os.environ.get('DOCKER_CLIENT_TIMEOUT'):
        timeout_value = os.environ.get('DOCKER_CLIENT_TIMEOUT')
        source = 'DOCKER_CLIENT_TIMEOUT'
    elif os.environ.get('COMPOSE_HTTP_TIMEOUT'):
        timeout_value = os.environ.get('COMPOSE_HTTP_TIMEOUT')
        source = 'COMPOSE_HTTP_TIMEOUT'
    if source:
        try:
            timeout = int(timeout_value)
        except ValueError:
            raise Exception("Error: {0} set to '{1}'. Expected an integer.".format(source, timeout_value))
    logger.debug("Setting Docker client timeout to {0}".format(timeout))
    return timeout


class Engine(BaseEngine, DockerSecretsMixin):

    # Capabilities of engine implementations
    CAP_BUILD_CONDUCTOR = True
    CAP_BUILD = True
    CAP_DEPLOY = True
    CAP_IMPORT = True
    CAP_INSTALL = True
    CAP_LOGIN = True
    CAP_PUSH = True
    CAP_RUN = True
    CAP_VERSION = True
    CAP_SIM_SECRETS = True

    COMPOSE_WHITELIST = (
        'links', 'depends_on', 'cap_add', 'cap_drop', 'command', 'devices',
        'dns', 'dns_opt', 'tmpfs', 'entrypoint', 'environment', 'expose',
        'external_links', 'extra_hosts', 'labels', 'links', 'logging', 'log_opt', 'networks',
        'network_mode', 'pids_limit', 'ports', 'security_opt', 'stop_grace_period',
        'stop_signal', 'sysctls', 'ulimits', 'userns_mode', 'volumes',
        'volume_driver', 'volumes_from', 'cpu_shares', 'cpu_quota', 'cpuset',
        'domainname', 'hostname', 'ipc', 'mac_address', 'mem_limit',
        'memswap_limit', 'mem_swappiness', 'mem_reservation', 'oom_score_adj',
        'privileged', 'read_only', 'restart', 'shm_size', 'stdin_open', 'tty',
        'user', 'working_dir'
    )
    display_name = u'Docker\u2122 daemon'

    _client = None

    FINGERPRINT_LABEL_KEY = 'com.ansible.container.fingerprint'
    ROLE_LABEL_KEY = 'com.ansible.container.role'
    LAYER_COMMENT = 'Built with Ansible Container (https://github.com/ansible/ansible-container)'

    @property
    def client(self):
        if not self._client:
            try:
                timeout = get_timeout()
                self._client = docker.from_env(version='auto', timeout=timeout)
            except DockerException as exc:
                if 'Connection refused' in str(exc):
                    raise exceptions.AnsibleContainerDockerConnectionRefused()
                elif 'Connection aborted' in str(exc):
                    raise exceptions.AnsibleContainerDockerConnectionAborted(u"%s" % str(exc))
                else:
                    raise
        return self._client

    @property
    def ansible_build_args(self):
        """Additional commandline arguments necessary for ansible-playbook runs during build"""
        return '-c docker'

    @property
    def ansible_orchestrate_args(self):
        """Additional commandline arguments necessary for ansible-playbook runs during orchestrate"""
        return '-c local'

    @property
    def default_registry_url(self):
        return u'https://index.docker.io/v1/'

    @property
    def default_registry_name(self):
        return u'Docker Hub'

    @property
    def auth_config_path(self):
        result = DOCKER_DEFAULT_CONFIG_PATH
        for path in DOCKER_CONFIG_FILEPATH_CASCADE:
            if path and os.path.exists(path):
                result = os.path.normpath(os.path.expanduser(path))
                break
        return result

    @property
    def secrets_mount_path(self):
        return os.path.join(os.sep, 'docker', 'secrets')

    def container_name_for_service(self, service_name):
        return u'%s_%s' % (self.project_name, service_name)

    def image_name_for_service(self, service_name):
        if service_name == 'conductor':
            return u'%s-%s' % (self.project_name.lower(), service_name.lower())
        result = None
        for name, service in iteritems(self.services):
            if service.get('containers'):
                for c in service['containers']:
                    container_service_name = u"%s-%s" % (name, c['container_name'])
                    if container_service_name == service_name:
                        if c.get('roles'):
                            result = u'%s-%s' % (self.project_name.lower(), container_service_name.lower())
                        else:
                            result = c.get('from')
                        break
            elif name == service_name:
                if service.get('roles'):
                    result = u'%s-%s' % (self.project_name.lower(), name.lower())
                else:
                    result = service.get('from')
            if result:
                break

        if result is None:
            raise exceptions.AnsibleContainerConfigException(
                u"Failed to resolve image for service {}. The service or container definition "
                u"is likely missing a 'from' attribute".format(service_name)
            )
        return result

    def run_kwargs_for_service(self, service_name):
        to_return = self.services[service_name].copy()
        # remove keys that docker-compose format doesn't accept, or that can't
        #  be used during the build phase
        container_args = inspect.getargspec(ContainerApiMixin.create_container)[0] + RUN_HOST_CONFIG_KWARGS
        remove_keys = list(set(to_return.keys()) - set(container_args)) + ['links']
        logger.debug("Removing keys", keys=remove_keys)
        for key in list(remove_keys):
            try:
                to_return.pop(key)
            except KeyError:
                pass
        if to_return.get('ports'):
            # convert ports from a list to a dict that docker-py likes
            new_ports = build_port_bindings(to_return.get('ports'))
            to_return['ports'] = new_ports
        return to_return

    @host_only
    def print_version_info(self):
        print(json.dumps(self.client.info(), indent=2))
        print(json.dumps(self.client.version(), indent=2))

    @log_runs
    @conductor_only
    def run_container(self, image_id, service_name, **kwargs):
        """Run a particular container. The kwargs argument contains individual
        parameter overrides from the service definition."""
        run_kwargs = self.run_kwargs_for_service(service_name)
        run_kwargs.update(kwargs, relax=True)
        logger.debug('Running container in docker', image=image_id, params=run_kwargs)

        container_obj = self.client.containers.run(
            image=image_id,
            detach=True,
            **run_kwargs
        )

        log_iter = container_obj.logs(stdout=True, stderr=True, stream=True)
        mux = logmux.LogMultiplexer()
        mux.add_iterator(log_iter, plainLogger)
        return container_obj.id

    @log_runs
    @host_only
    def run_conductor(self, command, config, base_path, params, engine_name=None, volumes=None):
        image_id = self.get_latest_image_id_for_service('conductor')
        if image_id is None:
            raise exceptions.AnsibleContainerConductorException(
                    u"Conductor container can't be found. Run "
                    u"`ansible-container build` first")

        conductor_settings = config.get('settings', {}).get('conductor', {})

        if not volumes:
            volumes = {}

        def _add_volume(vol):
            volume_parts = vol.split(':')
            volume_parts[0] = os.path.normpath(os.path.abspath(os.path.expanduser(os.path.expandvars(volume_parts[0]))))
            volumes[volume_parts[0]] = {
                'bind': volume_parts[1] if len(volume_parts) > 1 else volume_parts[0],
                'mode': volume_parts[2] if len(volume_parts) > 2 else 'rw'
            }

        if params.get('with_volumes'):
            for volume in params.get('with_volumes'):
                _add_volume(volume)

        if conductor_settings.get('volumes'):
            for volume in conductor_settings['volumes']:
                _add_volume(volume)

        if command != 'destroy' and self.CAP_SIM_SECRETS:
            self.create_secret_volume()
            volumes[self.secrets_volume_name] = {
                'bind': self.secrets_mount_path,
                'mode': 'rw'
            }

        pswd_file = params.get('vault_password_file') or config.get('settings', {}).get('vault_password_file')
        if pswd_file:
            pswd_file_path = os.path.normpath(os.path.abspath(os.path.expanduser(pswd_file)))
            if not os.path.exists(pswd_file_path):
                logger.warning(u'Vault file %s specified but does not exist. Ignoring it.',
                               pswd_file_path)
            else:
                volumes[pswd_file_path] = {
                    'bind': pswd_file_path,
                    'mode': 'ro'
                }
                params['vault_password_file'] = pswd_file_path

        vaults = params.get('vault_files') or config.get('settings', {}).get('vault_files')
        if vaults:
            vault_paths = [os.path.normpath(os.path.abspath(os.path.expanduser(v))) for v in vaults]
            for vault_path in vault_paths:
                if not os.path.exists(vault_path):
                    logger.warning(u'Vault file %s specified but does not exist. Ignoring it.',
                                   vault_path)
                    continue
                volumes[vault_path] = {
                    'bind': vault_path,
                    'mode': 'ro'
                }
            params['vault_files'] = vault_paths

        permissions = 'ro' if command != 'install' else 'rw'
        if params.get('src_mount_path'):
            src_path = params['src_mount_path']
        else:
            src_path = base_path
        volumes[src_path] = {'bind': '/_src', 'mode': permissions}

        if params.get('deployment_output_path'):
            deployment_path = params['deployment_output_path']
            if not os.path.isdir(deployment_path):
                os.mkdir(deployment_path, 0o755)
            volumes[deployment_path] = {'bind': deployment_path, 'mode': 'rw'}

        roles_path = None
        if params.get('roles_path'):
            roles_path = params['roles_path']
        elif conductor_settings.get('roles_path'):
            roles_path = conductor_settings['roles_path']

        expanded_roles_path = []
        if roles_path:
            for role_path in roles_path:
                role_path = os.path.normpath(os.path.abspath(os.path.expanduser(role_path)))
                expanded_roles_path.append(role_path)
                volumes[role_path] = {'bind': role_path, 'mode': 'ro'}

        environ = {}
        if os.environ.get('DOCKER_HOST'):
            environ['DOCKER_HOST'] = os.environ['DOCKER_HOST']
            if os.environ.get('DOCKER_CERT_PATH'):
                environ['DOCKER_CERT_PATH'] = '/etc/docker'
                volumes[os.environ['DOCKER_CERT_PATH']] = {'bind': '/etc/docker',
                                                           'mode': 'ro'}
            if os.environ.get('DOCKER_TLS_VERIFY'):
                environ['DOCKER_TLS_VERIFY'] = os.environ['DOCKER_TLS_VERIFY']
        else:
            environ['DOCKER_HOST'] = 'unix:///var/run/docker.sock'
            volumes['/var/run/docker.sock'] = {'bind': '/var/run/docker.sock',
                                               'mode': 'rw'}

        def _add_var_list(vars):
            for var in vars:
                key, value = var.split('=', 1)
                environ[key] = value

        if params.get('with_variables'):
            _add_var_list(params['with_variables'])

        if conductor_settings.get('environment'):
            if isinstance(conductor_settings['environment'], dict):
                environ.update(conductor_settings['environment'])
            if isinstance(conductor_settings['environment'], list):
                _add_var_list(conductor_settings['environment'])

        if roles_path:
            environ['ANSIBLE_ROLES_PATH'] = "%s:/src/roles:/etc/ansible/roles" % (':').join(expanded_roles_path)
        else:
            environ['ANSIBLE_ROLES_PATH'] = '/src/roles:/etc/ansible/roles'

        if params.get('devel'):
            conductor_path = os.path.dirname(container.__file__)
            logger.debug(u"Binding Ansible Container code at %s into conductor "
                         u"container", conductor_path)
            volumes[conductor_path] = {'bind': '/_ansible/container', 'mode': 'rw'}

        if command in ('login', 'push', 'build'):
            config_path = params.get('config_path') or self.auth_config_path
            create_file(config_path, '{}')
            volumes[config_path] = {'bind': config_path,
                                    'mode': 'rw'}

        if not engine_name:
            engine_name = __name__.rsplit('.', 2)[-2]

        serialized_params = base64.b64encode(json.dumps(params).encode("utf-8")).decode()
        serialized_config = base64.b64encode(json.dumps(ordereddict_to_list(config)).encode("utf-8")).decode()

        run_kwargs = dict(
            name=self.container_name_for_service('conductor'),
            command=['conductor',
                     command,
                     '--project-name', self.project_name,
                     '--engine', engine_name,
                     '--params', serialized_params,
                     '--config', serialized_config,
                     '--encoding', 'b64json'],
            detach=True,
            user='root',
            volumes=volumes,
            environment=environ,
            working_dir='/src',
            cap_add=['SYS_ADMIN']
        )

        # Anytime a playbook is executed, /src is bind mounted to a tmpdir, and that seems to
        # require privileged=True
        run_kwargs['privileged'] = True

        # Support optional volume driver for mounting named volumes to the Conductor
        if params.get('volume_driver'):
            run_kwargs['volume_driver'] = params['volume_driver']

        logger.debug('Docker run:', image=image_id, params=run_kwargs)
        try:
            container_obj = self.client.containers.run(
                image_id,
                **run_kwargs
            )
        except docker_errors.APIError as exc:
            if exc.response.status_code == StatusCodes.CONFLICT:
                raise exceptions.AnsibleContainerConductorException(
                    u"Can't start conductor container, another conductor for "
                    u"this project already exists or wasn't cleaned up.")
            reraise(*sys.exc_info())
        else:
            log_iter = container_obj.logs(stdout=True, stderr=True, stream=True)
            mux = logmux.LogMultiplexer()
            mux.add_iterator(log_iter, plainLogger)
            return container_obj.id

    def await_conductor_command(self, command, config, base_path, params, save_container=False):
        conductor_id = self.run_conductor(command, config, base_path, params)
        try:
            while self.service_is_running('conductor'):
                time.sleep(0.1)
        finally:
            exit_code = self.service_exit_code('conductor')
            msg = 'Preserving as requested.' if save_container else 'Cleaning up.'
            logger.info('Conductor terminated. {}'.format(msg), save_container=save_container,
                        conductor_id=conductor_id, command_rc=exit_code)
            if not save_container:
                self.delete_container(conductor_id, remove_volumes=True)

            if exit_code:
                raise exceptions.AnsibleContainerConductorException(
                    u'Conductor exited with status %s' % exit_code
                )
            elif command in ('run', 'destroy', 'stop', 'restart') and params.get('deployment_output_path') \
                    and not self.debug:
                # Remove any ansible-playbook residue
                output_path = params['deployment_output_path']
                for path in ('files', 'templates'):
                    shutil.rmtree(os.path.join(output_path, path), ignore_errors=True)
                if not self.devel:
                    for filename in ('playbook.retry', 'playbook.yml', 'hosts'):
                        if os.path.exists(os.path.join(output_path, filename)):
                            os.remove(os.path.join(output_path, filename))

    def service_is_running(self, service, container_id=None):
        try:
            running_container = self.client.containers.get(
                container_id or self.container_name_for_service(service))
            return running_container.status == 'running' and running_container.id
        except docker_errors.NotFound:
            return False

    def service_exit_code(self, service, container_id=None):
        try:
            container_info = self.client.api.inspect_container(
                container_id or self.container_name_for_service(service))
            return container_info['State']['ExitCode']
        except docker_errors.APIError:
            return None

    def start_container(self, container_id):
        try:
            to_start = self.client.containers.get(container_id)
        except docker_errors.APIError:
            logger.debug(u"Could not find container %s to start", container_id,
                         id=container_id)
        else:
            to_start.start()
            log_iter = to_start.logs(stdout=True, stderr=True, stream=True)
            mux = logmux.LogMultiplexer()
            mux.add_iterator(log_iter, plainLogger)
            return to_start.id

    def stop_container(self, container_id, forcefully=False):
        try:
            to_stop = self.client.containers.get(container_id)
        except docker_errors.APIError:
            logger.debug(u"Could not find container %s to stop", container_id,
                         id=container_id, force=forcefully)
            pass
        else:
            if forcefully:
                to_stop.kill()
            else:
                to_stop.stop(timeout=60)

    def restart_all_containers(self):
        raise NotImplementedError()

    def inspect_container(self, container_id):
        try:
            return self.client.api.inspect_container(container_id)
        except docker_errors.APIError:
            return None

    def delete_container(self, container_id, remove_volumes=False):
        try:
            to_delete = self.client.containers.get(container_id)
        except docker_errors.APIError:
            pass
        else:
            to_delete.remove(v=remove_volumes)

    def get_image_id_for_container_id(self, container_id):
        try:
            container_info = self.client.containers.get(container_id)
        except docker_errors.NotFound:
            logger.debug("Could not find container for %s", container_id,
                         all_containers=self.client.containers.list())
            return None
        else:
            return container_info.image.id

    def get_container_id_by_name(self, name):
        try:
            container_info = self.client.containers.get(name)
        except docker_errors.NotFound:
            logger.debug("Could not find container for %s", name,
                         all_containers=[
                             c.name for c in self.client.containers.list(all=True)])
            return None
        else:
            return container_info.id

    def get_intermediate_containers_for_service(self, service_name):
        container_substring = self.container_name_for_service(service_name)
        for container in self.client.containers.list(all=True):
            if container.name.startswith(container_substring) and \
                            container.name != container_substring:
                yield container.name

    def get_image_id_by_fingerprint(self, fingerprint):
        try:
            image = self.client.images.list(
                all=True,
                filters=dict(label='%s=%s' % (self.FINGERPRINT_LABEL_KEY,
                                              fingerprint)))[0]
        except IndexError:
            return None
        else:
            return image.id

    def get_fingerprint_for_image_id(self, image_id):
        labels = self.get_image_labels(image_id)
        return labels.get(self.FINGERPRINT_LABEL_KEY)

    def get_image_id_by_tag(self, tag):
        try:
            image = self.client.images.get(tag)
            return image.id
        except docker_errors.ImageNotFound:
            return None

    def get_image_labels(self, image_id):
        try:
            image = self.client.images.get(image_id)
        except docker_errors.ImageNotFound:
            return {}
        else:
            return image.attrs['Config']['Labels']

    def get_latest_image_id_for_service(self, service_name):
        image = self.get_latest_image_for_service(service_name)
        if image is not None:
            return image.id
        return None

    def get_latest_image_for_service(self, service_name):
        try:
            image = self.client.images.get(
                '%s:latest' % self.image_name_for_service(service_name))
        except docker_errors.ImageNotFound:
            images = self.client.images.list(name=self.image_name_for_service(service_name))
            logger.debug(
                u"Could not find the latest image for service, "
                u"searching for other tags with same image name",
                image_name=self.image_name_for_service(service_name),
                service=service_name)

            if not images:
                return None

            def tag_sort(i):
                return [t for t in i.tags if t.startswith(self.image_name_for_service(service_name))][0]

            images = sorted(images, key=tag_sort)
            logger.debug('Found images for service',
                         service=service_name, images=images)
            return images[-1]
        else:
            return image

    def containers_built_for_services(self, services):
        # Verify all images are built
        for service_name in services:
            logger.info(u'Verifying service image', service=service_name)
            image_id = self.get_latest_image_id_for_service(service_name)
            if image_id is None:
                raise exceptions.AnsibleContainerMissingImage(
                    u"Missing image for service '{}'. Run 'ansible-container build' to (re)create it."
                    .format(service_name)
                )

    def get_build_stamp_for_image(self, image_id):
        build_stamp = None
        try:
            image = self.client.images.get(image_id)
        except docker_errors.ImageNotFound:
            raise exceptions.AnsibleContainerConductorException(
                "Unable to find image {}".format(image_id)
            )
        if image and image.tags:
            build_stamp = [tag for tag in image.tags if not tag.endswith(':latest')][0].split(':')[-1]
        return build_stamp

    @conductor_only
    def pull_image_by_tag(self, image):
        repo = image
        tag = 'latest'
        if ':' in image:
            repo, tag = image.rsplit(':',1)
        logger.debug("Pulling image {}:{}".format(repo, tag))
        try:
            image_id = self.client.images.pull(repo, tag=tag)
        except docker_errors.APIError as exc:
            raise exceptions.AnsibleContainerException("Failed to pull {}: {}".format(image, str(exc)))
        return image_id

    @log_runs
    @conductor_only
    def flatten_container(self,
                          container_id,
                          service_name,
                          metadata):
        image_name = self.image_name_for_service(service_name)
        image_version = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
        image_config = utils.metadata_to_image_config(metadata)

        to_squash = self.client.containers.get(container_id)
        raw_image = to_squash.export()

        logger.debug("Exported service container as tarball", container=image_name)

        out = self.client.api.import_image_from_data(
            raw_image,
            repository=image_name,
            tag=image_version
        )
        logger.debug("Committed flattened image", out=out)

        image_id = json.loads(out)['status']

        self.tag_image_as_latest(service_name, image_id.split(':')[-1])

        return image_id


    @log_runs
    @conductor_only
    def commit_role_as_layer(self,
                             container_id,
                             service_name,
                             fingerprint,
                             role_name,
                             metadata,
                             with_name=False):
        metadata = metadata.copy()
        to_commit = self.client.containers.get(container_id)
        image_name = self.image_name_for_service(service_name)
        image_version = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
        image_changes = []
        volume_specs = metadata.pop('volumes', [])
        for volume_spec in volume_specs:
            if ':' in volume_spec and not volume_spec.startswith(('/', '$')):
                mount_point = volume_spec.split(':', 1)[-1]
            elif ':' not in volume_spec:
                mount_point = volume_spec
            else:
                continue
            image_changes.append(u'VOLUME %s' % (mount_point,))
        image_config = utils.metadata_to_image_config(metadata)
        image_config.setdefault('Labels', {})[self.FINGERPRINT_LABEL_KEY] = fingerprint
        image_config['Labels'][self.ROLE_LABEL_KEY] = role_name
        commit_data = dict(
            repository=image_name if with_name else None,
            tag=image_version if with_name else None,
            message=self.LAYER_COMMENT,
            conf=image_config,
            changes=u'\n'.join(image_changes)
        )
        logger.debug('Committing new layer', params=commit_data)
        return to_commit.commit(**commit_data).id

    def tag_image_as_latest(self, service_name, image_id):
        image_obj = self.client.images.get(image_id)
        image_obj.tag(self.image_name_for_service(service_name), 'latest')

    @conductor_only
    def _get_top_level_secrets(self):
        """
        Convert the top-level 'secrets' directive to the Docker format
        :return: secrets dict
        """
        top_level_secrets = dict()
        if self.secrets:
            for secret, secret_definition in iteritems(self.secrets):
                if isinstance(secret_definition, dict):
                    for key, value in iteritems(secret_definition):
                        name = '{}_{}'.format(secret, key)
                        top_level_secrets[name] = dict(external=True)
                elif isinstance(secret_definition, string_types):
                    top_level_secrets[secret] = dict(external=True)
        return top_level_secrets

    @conductor_only
    def generate_orchestration_playbook(self, url=None, namespace=None, vault_files=None, **kwargs):
        """
        Generate an Ansible playbook to orchestrate services.
        :param url: registry URL where images will be pulled from
        :param namespace: registry namespace
        :return: playbook dict
        """
        states = ['start', 'restart', 'stop', 'destroy']
        service_def = {}
        for service_name, service in iteritems(self.services):
            service_definition = {}
            if service.get('roles'):
                if url and namespace:
                    # Reference previously pushed image
                    service_definition[u'image'] = '{}/{}/{}'.format(re.sub(r'/$', '', url), namespace,
                                                                     self.image_name_for_service(service_name))
                else:
                    # Check that the image was built
                    image = self.get_latest_image_for_service(service_name)
                    if image is None:
                        raise exceptions.AnsibleContainerConductorException(
                            u"No image found for service {}, make sure you've run `ansible-container "
                            u"build`".format(service_name)
                        )
                    service_definition[u'image'] = image.tags[0]
            else:
                try:
                    # Check if the image is already local
                    image = self.client.images.get(service['from'])
                    image_from = image.tags[0]
                except docker.errors.ImageNotFound:
                    image_from = service['from']
                    logger.warning(u"Image {} for service {} not found. "
                                   u"An attempt will be made to pull it.".format(service['from'], service_name))
                service_definition[u'image'] = image_from

            for extra in self.COMPOSE_WHITELIST:
                if extra in service:
                    service_definition[extra] = service[extra]

            if 'secrets' in service:
                service_secrets = []
                for secret, secret_engines in iteritems(service[u'secrets']):
                    if 'docker' in secret_engines:
                        service_secrets += secret_engines[u'docker']
                if service_secrets:
                    service_definition[u'secrets'] = service_secrets
                if self.CAP_SIM_SECRETS:
                    # Simulate external secrets using a Docker volume
                    if not 'volumes' in service_definition:
                        service_definition['volumes'] = []
                    service_definition['volumes'].append("{}:/run/secrets:ro".format(self.secrets_volume_name))

            logger.debug(u'Adding new service to definition',
                         service=service_name, definition=service_definition)
            service_def[service_name] = service_definition

        tasks = []

        top_level_secrets = self._get_top_level_secrets()
        if self.CAP_SIM_SECRETS and top_level_secrets:
            # Let compose know that we're using a named volume to simulate external secrets
            if not isinstance(self.volumes, dict):
                self.volumes = dict()
            self.volumes[self.secrets_volume_name] = dict(external=True)

        for desired_state in states:
            task_params = {
                u'project_name': self.project_name,
                u'definition': {
                    u'version': u'3.1' if top_level_secrets else u'2',
                    u'services': service_def,
                }
            }
            if self.secrets:
                task_params[u'definition'][u'secrets'] = top_level_secrets
            if self.volumes:
                task_params[u'definition'][u'volumes'] = dict(self.volumes)

            if desired_state in {'restart', 'start', 'stop'}:
                task_params[u'state'] = u'present'
                if desired_state == 'restart':
                    task_params[u'restarted'] = True
                if desired_state == 'stop':
                    task_params[u'stopped'] = True
            elif desired_state == 'destroy':
                task_params[u'state'] = u'absent'
                task_params[u'remove_volumes'] = u'yes'

            tasks.append({u'docker_service': task_params, u'tags': [desired_state]})

        playbook = []

        if self.secrets and self.CAP_SIM_SECRETS:
            playbook.append(self.generate_secrets_play(vault_files=vault_files))

        playbook.append(CommentedMap([
            (u'name', 'Deploy {}'.format(self.project_name)),
            (u'hosts', u'localhost'),
            (u'gather_facts', False)
        ]))

        if vault_files:
            playbook[len(playbook) - 1][u'vars_files'] = [os.path.normpath(os.path.abspath(v)) for v in vault_files]
        playbook[len(playbook) - 1][u'tasks'] = tasks

        for service in list(self.services.keys()) + ['conductor']:
            image_name = self.image_name_for_service(service)
            for image in self.client.images.list(name=image_name):
                logger.debug('Found image for service', tags=image.tags, id=image.short_id)
                for tag in image.tags:
                    if tag.startswith(self.project_name):
                        logger.debug('Adding task to destroy image', tag=tag)
                        playbook[len(playbook) - 1][u'tasks'].append({
                            u'docker_image': {
                                u'name': tag,
                                u'state': u'absent',
                                u'force': u'yes'
                            },
                            u'tags': u'destroy'
                        })

        if self.secrets and self.CAP_SIM_SECRETS:
            playbook.append(self.generate_remove_volume_play())

        logger.debug(u'Created playbook to run project', playbook=playbook)
        return playbook

    @conductor_only
    def push(self, image_id, service_name, tag=None, namespace=None, url=None, username=None, password=None,
             repository_prefix=None, **kwargs):
        """
        Push an image to a remote registry.
        """
        auth_config = {
            'username': username,
            'password': password
        }

        build_stamp = self.get_build_stamp_for_image(image_id)
        tag = tag or build_stamp

        if repository_prefix:
            image_name = "{}-{}".format(repository_prefix, service_name)
        elif repository_prefix is None:
            image_name = "{}-{}".format(self.project_name, service_name)
        elif repository_prefix == '':
            image_name = service_name
        repository = "{}/{}".format(namespace, image_name)

        if url != self.default_registry_url:
            url = REMOVE_HTTP.sub('', url)
            repository = "%s/%s" % (url.rstrip('/'), repository)

        logger.info('Tagging %s' % repository)
        self.client.api.tag(image_id, repository, tag=tag)

        logger.info('Pushing %s:%s...' % (repository, tag))
        stream = self.client.api.push(repository, tag=tag, stream=True, auth_config=auth_config)

        last_status = None
        for data in stream:
            data = data.splitlines()
            for line in data:
                line = json.loads(line)
                if type(line) is dict and 'error' in line:
                    plainLogger.error(line['error'])
                    raise exceptions.AnsibleContainerException(
                        "Failed to push image. {}".format(line['error'])
                    )
                elif type(line) is dict and 'status' in line:
                    if line['status'] != last_status:
                        plainLogger.info(line['status'])
                    last_status = line['status']
                else:
                    plainLogger.debug(line)

    @staticmethod
    def _prepare_prebake_manifest(base_path, base_image, temp_dir, tarball):
        utils.jinja_render_to_temp(TEMPLATES_PATH,
                                   'conductor-src-dockerfile.j2', temp_dir,
                                   'Dockerfile',
                                   conductor_base=base_image,
                                   docker_version=DOCKER_VERSION)

        tarball.add(os.path.join(temp_dir, 'Dockerfile'),
                    arcname='Dockerfile')

        utils.jinja_render_to_temp(TEMPLATES_PATH,
                                   'atomic-help.j2', temp_dir,
                                   'help.1',
                                   ansible_container_version=container.__version__)
        tarball.add(os.path.join(temp_dir, 'help.1'),
                    arcname='help.1')

        utils.jinja_render_to_temp(TEMPLATES_PATH,
                                   'license.j2', temp_dir,
                                   'LICENSE')
        tarball.add(os.path.join(temp_dir, 'LICENSE'),
                    arcname='LICENSE')

        container_dir = os.path.dirname(container.__file__)
        tarball.add(container_dir, arcname='container-src')
        package_dir = os.path.dirname(container_dir)

        # For an editable install, the setup.py and requirements.* will be
        # available in the package_dir. Otherwise, our custom sdist (see
        # setup.py) would have moved them to FILES_PATH
        setup_py_dir = (package_dir
                        if os.path.exists(os.path.join(package_dir, 'setup.py'))
                        else FILES_PATH)
        req_txt_dir = (package_dir
                       if os.path.exists(
            os.path.join(package_dir, 'conductor-requirements.txt'))
                       else FILES_PATH)
        req_yml_dir = (package_dir
                       if os.path.exists(
            os.path.join(package_dir, 'conductor-requirements.yml'))
                       else FILES_PATH)
        tarball.add(os.path.join(setup_py_dir, 'setup.py'),
                    arcname='container-src/conductor-build/setup.py')
        tarball.add(os.path.join(req_txt_dir, 'conductor-requirements.txt'),
                    arcname='container-src/conductor-build/conductor'
                            '-requirements.txt')
        tarball.add(os.path.join(req_yml_dir, 'conductor-requirements.yml'),
                    arcname='container-src/conductor-build/conductor-requirements.yml')

    def _prepare_conductor_manifest(self, base_path, base_image, temp_dir, tarball, conductor_provider="ansible"):
        source_dir = os.path.normpath(base_path)

        for filename in ['ansible.cfg', 'ansible-requirements.txt',
                         'requirements.yml']:
            file_path = os.path.join(source_dir, filename)
            if os.path.exists(filename):
                tarball.add(file_path,
                            arcname=os.path.join('build-src', filename))
        # Make an empty file just to make sure the build-src dir has something
        open(os.path.join(temp_dir, '.touch'), 'w')
        tarball.add(os.path.join(temp_dir, '.touch'),
                    arcname='build-src/.touch')

        prebaked = base_image in reduce(lambda x, y: x + [y[0]] + y[1],
                                        PREBAKED_DISTROS.items(), [])
        if prebaked:
            base_image = [k for k, v in PREBAKED_DISTROS.items()
                              if base_image in [k] + v][0]
            conductor_base = 'container-conductor-%s:%s' % (
                base_image.replace(':', '-'),
                container.__version__
            )
            if not self.get_image_id_by_tag(conductor_base):
                conductor_base = '%s/%s' % (conductor_provider, conductor_base)
        else:
            conductor_base = 'container-conductor-%s:%s' % (
                base_image.replace(':', '-'),
                container.__version__
            )

        run_commands = []
        if modules_to_install(base_path):
            run_commands.append('pip install --no-cache-dir -r /_ansible/build/ansible-requirements.txt')
        if roles_to_install(base_path):
            run_commands.append('ansible-galaxy install -p /etc/ansible/roles -r /_ansible/build/requirements.yml')
        if ansible_config_exists(base_path):
            run_commands.append('cp /_ansible/build/ansible.cfg /etc/ansible/ansible.cfg')
        separator = ' && \\\r\n'
        install_requirements = separator.join(run_commands)

        utils.jinja_render_to_temp(TEMPLATES_PATH,
                                   'conductor-local-dockerfile.j2', temp_dir,
                                   'Dockerfile',
                                   install_requirements=install_requirements,
                                   original_base=base_image,
                                   conductor_base=conductor_base,
                                   docker_version=DOCKER_VERSION)
        tarball.add(os.path.join(temp_dir, 'Dockerfile'),
                    arcname='Dockerfile')

    @log_runs
    @host_only
    def build_conductor_image(self, base_path, base_image, prebaking=False, cache=True, environment=None, conductor_provider="ansible"):
        if environment is None:
            environment = []
        with utils.make_temp_dir() as temp_dir:
            logger.info('Building Docker Engine context...')
            tarball_path = os.path.join(temp_dir, 'context.tar')
            tarball_file = open(tarball_path, 'wb')
            tarball = tarfile.TarFile(fileobj=tarball_file,
                                      mode='w')
            source_dir = os.path.normpath(base_path)

            for filename in ['ansible.cfg', 'ansible-requirements.txt',
                             'requirements.yml']:
                file_path = os.path.join(source_dir, filename)
                if os.path.exists(file_path):
                    tarball.add(file_path,
                                arcname=os.path.join('build-src', filename))
            # Make an empty file just to make sure the build-src dir has something
            open(os.path.join(temp_dir, '.touch'), 'w')
            tarball.add(os.path.join(temp_dir, '.touch'), arcname='build-src/.touch')

            tarball.add(os.path.join(FILES_PATH, 'get-pip.py'),
                        arcname='contrib/get-pip.py')

            container_dir = os.path.dirname(container.__file__)
            tarball.add(container_dir, arcname='container-src')
            package_dir = os.path.dirname(container_dir)

            # For an editable install, the setup.py and requirements.* will be
            # available in the package_dir. Otherwise, our custom sdist (see
            # setup.py) would have moved them to FILES_PATH
            setup_py_dir = (package_dir
                            if os.path.exists(os.path.join(package_dir, 'setup.py'))
                            else FILES_PATH)
            req_txt_dir = (package_dir
                           if os.path.exists(os.path.join(package_dir, 'conductor-requirements.txt'))
                           else FILES_PATH)
            req_yml_dir = (package_dir
                           if os.path.exists(os.path.join(package_dir, 'conductor-requirements.yml'))
                           else FILES_PATH)
            for filename in ['pycharm-debug.egg']:
                file_path = os.path.join(setup_py_dir, filename)
                if os.path.exists(file_path):
                    tarball.add(file_path,
                                arcname=os.path.join('build-src', filename))
            tarball.add(os.path.join(setup_py_dir, 'setup.py'),
                        arcname='container-src/conductor-build/setup.py')
            tarball.add(os.path.join(req_txt_dir, 'conductor-requirements.txt'),
                            arcname='container-src/conductor-build/conductor-requirements.txt')
            tarball.add(os.path.join(req_yml_dir, 'conductor-requirements.yml'),
                        arcname='container-src/conductor-build/conductor-requirements.yml')

            utils.jinja_render_to_temp(TEMPLATES_PATH,
                                       'conductor-src-dockerfile.j2', temp_dir,
                                       'Dockerfile',
                                       conductor_base=base_image,
                                       docker_version=DOCKER_VERSION,
                                       environment=environment)
            tarball.add(os.path.join(temp_dir, 'Dockerfile'),
                        arcname='Dockerfile')

            if prebaking:
                self.client.images.pull(*base_image.split(':', 1))
                self._prepare_prebake_manifest(base_path, base_image, temp_dir,
                                               tarball)
                tag = 'container-conductor-%s:%s' % (base_image.replace(':', '-'),
                                                     container.__version__)
            else:
                self._prepare_conductor_manifest(base_path, base_image, temp_dir,
                                                 tarball, conductor_provider)
                tag = self.image_name_for_service('conductor')
            logger.debug('Context manifest:')
            for tarinfo_obj in tarball.getmembers():
                logger.debug('tarball item: %s (%s bytes)', tarinfo_obj.name,
                             tarinfo_obj.size, file=tarinfo_obj.name,
                             bytes=tarinfo_obj.size, terse=True)
            tarball.close()
            tarball_file.close()
            tarball_file = open(tarball_path, 'rb')
            logger.info('Starting Docker build of Ansible Container Conductor image (please be patient)...')
            # FIXME: Error out properly if build of conductor fails.
            if self.debug:
                for line in self.client.api.build(fileobj=tarball_file,
                                                  custom_context=True,
                                                  tag=tag,
                                                  rm=True,
                                                  decode=True,
                                                  nocache=not cache):
                    try:
                        if line.get('status') == 'Downloading':
                            # skip over lines that give spammy byte-by-byte
                            # progress of downloads
                            continue
                        elif 'errorDetail' in line:
                            raise exceptions.AnsibleContainerException(
                                "Error building conductor image: {0}".format(line['errorDetail']['message']))
                    except ValueError:
                        pass
                    except exceptions.AnsibleContainerException:
                        raise

                    # this bypasses the fancy colorized logger for things that
                    # are just STDOUT of a process
                    plainLogger.debug(text.to_text(line.get('stream', json.dumps(line))).rstrip())
                return self.get_image_id_by_tag(tag)
            else:
                image = self.client.images.build(fileobj=tarball_file,
                                                 custom_context=True,
                                                 tag=tag,
                                                 rm=True,
                                                 nocache=not cache)
                return image.id

    def get_runtime_volume_id(self, mount_point):
        try:
            container_data = self.client.api.inspect_container(
                self.container_name_for_service('conductor')
            )
        except docker_errors.APIError:
            raise ValueError('Conductor container not found.')
        mounts = container_data['Mounts']
        try:
            usr_mount, = [mount for mount in mounts if mount['Destination'] == mount_point]
        except ValueError:
            raise ValueError('Runtime volume %s not found on Conductor' % mount_point)
        return usr_mount['Name']

    @host_only
    def import_project(self, base_path, import_from, bundle_files=False, force=False, **kwargs):
        from .importer import DockerfileImport

        dfi = DockerfileImport(base_path,
                               self.project_name,
                               import_from,
                               bundle_files,
                               force)

        dfi.run()

    @conductor_only
    def login(self, username, password, email, url, config_path):
        """
        If username and password are provided, authenticate with the registry.
        Otherwise, check the config file for existing authentication data.
        """
        if username and password:
            try:
                self.client.login(username=username, password=password, email=email,
                                  registry=url, reauth=True)
            except docker_errors.APIError as exc:
                raise exceptions.AnsibleContainerConductorException(
                    u"Error logging into registry: {}".format(exc)
                )
            except Exception:
                raise

            self._update_config_file(username, password, email, url, config_path)

        username, password = self._get_registry_auth(url, config_path)
        if not username:
            raise exceptions.AnsibleContainerConductorException(
                u'Please provide login credentials for registry {}.'.format(url))
        return username, password

    @staticmethod
    @conductor_only
    def _update_config_file(username, password, email, url, config_path):
        """Update the config file with the authorization."""
        try:
            # read the existing config
            config = json.load(open(config_path, "r"))
        except ValueError:
            config = dict()

        if not config.get('auths'):
            config['auths'] = dict()

        if not config['auths'].get(url):
            config['auths'][url] = dict()
        encoded_credentials = dict(
            auth=base64.b64encode(username + b':' + password),
            email=email
        )
        config['auths'][url] = encoded_credentials
        try:
            json.dump(config, open(config_path, "w"), indent=5, sort_keys=True)
        except Exception as exc:
            raise exceptions.AnsibleContainerConductorException(
                u"Failed to write registry config to {0} - {1}".format(config_path, exc)
            )

    @staticmethod
    @conductor_only
    def _get_registry_auth(registry_url, config_path):
        """
        Retrieve from the config file the current authentication for a given URL, and
        return the username, password
        """
        username = None
        password = None
        try:
            docker_config = json.load(open(config_path))
        except ValueError:
            # The configuration file is empty
            return username, password
        if docker_config.get('auths'):
            docker_config = docker_config['auths']
        auth_key = docker_config.get(registry_url, {}).get('auth', None)
        if auth_key:
            username, password = base64.b64decode(auth_key).split(':', 1)
        return username, password

    @conductor_only
    def pre_deployment_setup(self, project_name, services, **kwargs):
        pass
