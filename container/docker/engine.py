# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
plainLogger = logging.getLogger(__name__)

from ..common.visibility import getLogger
logger = getLogger(__name__)

import os
import sys
import base64
import json
import six
import tarfile
try:
    import httplib as StatusCodes
except ImportError:
    from http import HTTPStatus as StatusCodes

try:
    import docker
    from docker import errors as docker_errors
except ImportError:
    raise ImportError('Use of this engine requires you "pip install \'docker>=2.1\'" first.')

from ..common.docker import DockerEngineUtilityMixin
from ..common import exceptions, logmux, utils
from ..common.utils import log_runs
from ..engine import BaseEngine

DOCKER_VERSION = '1.13.1'

TEMPLATES_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        'templates'))

FILES_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        'files'))


class Engine(DockerEngineUtilityMixin, BaseEngine):
    CAP_BUILD_CONDUCTOR = True
    CAP_BUILD = True
    CAP_DEPLOY = True
    CAP_IMPORT = True
    CAP_LOGIN = True
    CAP_PUSH = True
    CAP_RUN = True

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

            import container
            src_dir = os.path.dirname(container.__file__)

            tarball.add(src_dir, arcname='container-src')

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

    def import_project(self, base_path, import_from, bundle_files=False, **kwargs):
        from .importer import DockerfileImport

        dfi = DockerfileImport(base_path,
                               self.project_name,
                               import_from,
                               bundle_files)
        dfi.run()
