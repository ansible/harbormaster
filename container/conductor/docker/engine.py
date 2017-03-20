# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
plainLogger = logging.getLogger(__name__)

from ..visibility import getLogger
logger = getLogger(__name__)

import base64
import datetime
import functools
import inspect
import json
import os
import re
import six
import sys
import tarfile

try:
    import httplib as StatusCodes
except ImportError:
    from http import HTTPStatus as StatusCodes

from ..engine import BaseEngine
from .. import utils
from .. import logmux
from .. import exceptions

try:
    import docker
    from docker import errors as docker_errors
    from docker.utils.ports import build_port_bindings
except ImportError:
    raise ImportError('Use of this engine requires you "pip install \'docker>=2.1\'" first.')

TEMPLATES_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        'templates'))

FILES_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        'files'))

DOCKER_VERSION = '1.13.1'

DOCKER_DEFAULT_CONFIG_PATH = os.path.join(os.environ.get('HOME', ''), '.docker', 'config.json')

DOCKER_CONFIG_FILEPATH_CASCADE = [
    os.environ.get('DOCKER_CONFIG', ''),
    DOCKER_DEFAULT_CONFIG_PATH,
    os.path.join(os.environ.get('HOME', ''), '.dockercfg')
]

REMOVE_HTTP = re.compile('^https?://')

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


class Engine(BaseEngine):

    # Capabilities of engine implementations
    CAP_BUILD_CONDUCTOR = True
    CAP_BUILD = True
    CAP_DEPLOY = True
    CAP_IMPORT = True
    CAP_LOGIN = True
    CAP_PUSH = True
    CAP_RUN = True

    display_name = u'Docker\u2122 daemon'

    _client = None
    _api_client = None

    FINGERPRINT_LABEL_KEY = 'com.ansible.container.fingerprint'
    LAYER_COMMENT = 'Built with Ansible Container (https://github.com/ansible/ansible-container)'

    @property
    def client(self):
        if not self._client:
            self._client = docker.from_env()
        return self._client

    @property
    def api_client(self):
        if not self._api_client:
            self._api_client = docker.APIClient()
        return self._api_client

    @property
    def ansible_args(self):
        """Additional commandline arguments necessary for ansible-playbook runs."""
        return u'-c docker'

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

    def container_name_for_service(self, service_name):
        return u'%s_%s' % (self.project_name, service_name)

    def image_name_for_service(self, service_name):
        return u'%s-%s' % (self.project_name, service_name)

    def run_kwargs_for_service(self, service_name):
        to_return = self.services[service_name].copy()
        for key in ['from', 'roles', 'shell']:
            try:
                to_return.pop(key)
            except KeyError:
                pass
        if to_return.get('ports'):
            # convert ports from a list to a dict that docker-py likes
            new_ports = build_port_bindings(to_return.get('ports'))
            to_return['ports'] = new_ports
        return to_return

    @log_runs
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
    def run_conductor(self, command, config, base_path, params):
        image_id = self.get_latest_image_id_for_service('conductor')
        if image_id is None:
            raise exceptions.AnsibleContainerConductorException(
                    u"Conductor container can't be found. Run "
                    u"`ansible-container build` first")
        serialized_params = base64.encodestring(json.dumps(params))
        serialized_config = base64.encodestring(json.dumps(config))
        volumes = {base_path: {'bind': '/src', 'mode': 'ro'}}
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

        environ['ANSIBLE_ROLES_PATH'] = '/src/roles:/etc/ansible/roles'

        if params.get('devel'):
            from container import conductor
            conductor_path = os.path.dirname(conductor.__file__)
            logger.debug(u"Binding conductor at %s into conductor container", conductor_path)
            volumes[conductor_path] = {'bind': '/_ansible/conductor/conductor', 'mode': 'rw'}

        if command in ('login', 'push') and params.get('config_path'):
            config_path = params.get('config_path')
            volumes[config_path] = {'bind': config_path,
                                    'mode': 'rw'}

        run_kwargs = dict(
            name=self.container_name_for_service('conductor'),
            command=['conductor',
                     command,
                     '--project-name', self.project_name,
                     '--engine', __name__.rsplit('.', 2)[-2],
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
            six.reraise(*sys.exc_info())
        else:
            log_iter = container_obj.logs(stdout=True, stderr=True, stream=True)
            mux = logmux.LogMultiplexer()
            mux.add_iterator(log_iter, plainLogger)
            return container_obj.id

    def service_is_running(self, service):
        try:
            container = self.client.containers.get(self.container_name_for_service(service))
            return container.status == 'running' and container.id
        except docker_errors.NotFound:
            return False

    def service_exit_code(self, service):
        try:
            container = self.client.api.inspect_container(self.container_name_for_service(service))
            return container['State']['ExitCode']
        except docker_errors.APIError:
            return None

    def stop_container(self, container_id, forcefully=False):
        try:
            container = self.client.containers.get(container_id)
        except docker_errors.APIError:
            pass
        else:
            if forcefully:
                container.kill()
            else:
                container.stop(timeout=60)

    def restart_all_containers(self):
        raise NotImplementedError()

    def inspect_container(self, container_id):
        try:
            return self.client.api.inspect_container(container_id)
        except docker_errors.APIError:
            return None

    def delete_container(self, container_id):
        try:
            container = self.client.containers.get(container_id)
        except docker_errors.APIError:
            pass
        else:
            container.remove()

    def get_container_id_for_service(self, service_name):
        try:
            container = self.client.containers.get(self.container_name_for_service(service_name))
        except docker_errors.NotFound:
            return None
        else:
            return container.id

    def get_image_id_by_fingerprint(self, fingerprint):
        try:
            image, = self.client.images.list(
                all=True,
                filters=dict(label='%s=%s' % (self.FINGERPRINT_LABEL_KEY,
                                              fingerprint)))
        except ValueError:
            return None
        else:
            return image.id

    def get_image_id_by_tag(self, tag):
        try:
            image = self.client.images.get(tag)
            return image.id
        except docker_errors.ImageNotFound:
            return None

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
            logger.debug("Could not find the latest image for service, "
                "searching for other tags with same image name",
                image_name=self.image_name_for_service(service_name),
                service=service_name)

            if not images:
                return None

            def tag_sort(i):
                return [t for t in i.tags if t.startswith(self.image_name_for_service(service_name))][0]

            images = sorted(images, key=tag_sort)
            logger.debug('Found images for service',
                    service=service_name,
                    images=images)
            return images[-1]
        else:
            return image

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

    @log_runs
    def commit_role_as_layer(self,
                             container_id,
                             service_name,
                             fingerprint,
                             metadata,
                             with_name=False):
        container = self.client.containers.get(container_id)
        image_name = self.image_name_for_service(service_name)
        image_version = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
        image_config = utils.metadata_to_image_config(metadata)
        image_config.setdefault('Labels', {})[self.FINGERPRINT_LABEL_KEY] = fingerprint
        commit_data = dict(repository=image_name if with_name else None,
            tag=image_version if with_name else None,
            message=self.LAYER_COMMENT,
            conf=image_config)
        logger.debug('Committing new layer', params=commit_data)
        return container.commit(**commit_data).id

    def tag_image_as_latest(self, service_name, image_id):
        image_obj = self.client.images.get(image_id)
        image_obj.tag(self.image_name_for_service(service_name), 'latest')

    def generate_orchestration_playbook(self, repository_data=None):
        """If repository_data is specified, presume to pull images from that
        repository. If not, presume the images are already present."""
        munged_services = {}

        for service_name, service in self.services.items():
            image = self.get_latest_image_for_service(service_name)
            runit = {
                'image': image.tags[0],
            }
            logger.debug('Adding new service to definition',
                service=service_name, definition=runit)
            munged_services[service_name] = runit

        playbook = [{
            'hosts': 'localhost',
            'gather_facts': False,
            'tasks': [
                {
                    'docker_service': {
                        'project_name': self.project_name,
                        'state': state,
                        'definition': {
                            'version': '2',
                            'services': munged_services,
                        }
                    }
                } for state in ('absent', 'present')
            ]
        }]
        logger.debug('Created playbook to run project', playbook=playbook)
        return playbook

    def push(self, image_id, service_name, repository_data):
        """
        Puse an image to a remote registry.
        """
        tag = repository_data.get('tag')
        namespace = repository_data.get('namespace')
        url = repository_data.get('url')
        auth_config = {
            'username': repository_data.get('username'),
            'password': repository_data.get('password')
        }

        build_stamp = self.get_build_stamp_for_image(image_id)
        tag = tag or build_stamp

        repository = "%s/%s-%s" % (namespace, self.project_name, service_name)
        if url != self.default_registry_url:
            url = REMOVE_HTTP.sub('', url)
            repository = "%s/%s" % (re.sub('/$', '', url), repository)

        logger.info('Tagging %s' % repository)
        self.api_client.tag(image_id, repository, tag=tag)

        logger.info('Pushing %s:%s...' % (repository, tag))
        stream = self.api_client.push(repository, tag=tag, stream=True, auth_config=auth_config)

        last_status = None
        for data in stream:
            data = data.splitlines()
            for line in data:
                line = json.loads(line)
                if type(line) is dict and 'error' in line:
                    plainLogger.error(line['error'])
                if type(line) is dict and 'status' in line:
                    if line['status'] != last_status:
                        plainLogger.info(line['status'])
                    last_status = line['status']
                else:
                    plainLogger.debug(line)

    @log_runs
    def build_conductor_image(self, base_path, base_image, cache=True):
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
                if os.path.exists(filename):
                    tarball.add(file_path,
                                arcname=os.path.join('build-src', filename))
            # Make an empty file just to make sure the build-src dir has something
            open(os.path.join(temp_dir, '.touch'), 'w')
            tarball.add(os.path.join(temp_dir, '.touch'), arcname='build-src/.touch')

            tarball.add(os.path.join(FILES_PATH, 'get-pip.py'),
                        arcname='contrib/get-pip.py')

            tarball.add(utils.conductor_dir, arcname='conductor-src/conductor')
            tarball.add(os.path.join(os.path.dirname(utils.conductor_dir),
                                     'conductor-setup.py'),
                        arcname='conductor-src/setup.py')
            tarball.add(os.path.join(os.path.dirname(utils.conductor_dir),
                                     'conductor-requirements.txt'),
                        arcname='conductor-src/requirements.txt')

            utils.jinja_render_to_temp(TEMPLATES_PATH,
                                       'conductor-dockerfile.j2', temp_dir,
                                       'Dockerfile',
                                       conductor_base=base_image,
                                       docker_version=DOCKER_VERSION)
            tarball.add(os.path.join(temp_dir, 'Dockerfile'),
                        arcname='Dockerfile')

            #for context_file in ['builder.sh', 'ansible-container-inventory.py',
            #                     'ansible.cfg', 'wait_on_host.py', 'ac_galaxy.py']:
            #    tarball.add(os.path.join(TEMPLATES_PATH, context_file),
            #                arcname=context_file)

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
                                                  tag=self.image_name_for_service('conductor'),
                                                  rm=True,
                                                  nocache=not cache):
                    try:
                        line_json = json.loads(line)
                        if 'stream' in line_json:
                            line = line_json['stream']
                        elif line_json.get('status') == 'Downloading':
                            # skip over lines that give spammy byte-by-byte
                            # progress of downloads
                            continue
                    except ValueError:
                        pass
                    # this bypasses the fancy colorized logger for things that
                    # are just STDOUT of a process
                    plainLogger.debug(line.rstrip())
                return self.get_latest_image_id_for_service('conductor')
            else:
                image = self.client.images.build(fileobj=tarball_file,
                                                 custom_context=True,
                                                 tag=self.image_name_for_service('conductor'),
                                                 rm=True,
                                                 nocache=not cache)
                return image.id

    def get_runtime_volume_id(self):
        try:
            container_data = self.client.api.inspect_container(
                self.container_name_for_service('conductor')
            )
        except docker_errors.APIError:
            raise ValueError('Conductor container not found.')
        mounts = container_data['Mounts']
        try:
            usr_mount, = [mount for mount in mounts if mount['Destination'] == '/usr']
        except ValueError:
            raise ValueError('Runtime volume not found on Conductor')
        return usr_mount['Name']

    def import_project(self, base_path, import_from, bundle_files=False, **kwargs):
        from .importer import DockerfileImport

        dfi = DockerfileImport(base_path,
                               self.project_name,
                               import_from,
                               bundle_files)
        dfi.run()

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

            self.update_config_file(username, password, email, url, config_path)

        username, password = self.get_registry_auth(url, config_path)
        if not username:
            raise exceptions.AnsibleContainerConductorException(
                u'Please provide login credentials for registry {}.'.format(url))
        return username, password

    @staticmethod
    def update_config_file(username, password, email, url, config_path):
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
    def get_registry_auth(registry_url, config_path):
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
            username, password = base64.decodestring(auth_key).split(':', 1)
        return username, password
