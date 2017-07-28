# -*- coding: utf-8 -*-
from __future__ import absolute_import

import json
import subprocess

try:
    import httplib as StatusCodes
except ImportError:
    from http import HTTPStatus as StatusCodes

from container import host_only, ENV
from container.docker.engine import Engine as DockerEngine
from container.utils.visibility import getLogger, log_runs

logger = getLogger(__name__)


# got to be named 'Engine'
class Engine(DockerEngine):

    # Capabilities of engine implementations
    CAP_BUILD_CONDUCTOR = False
    CAP_BUILD = True
    CAP_DEPLOY = False
    CAP_IMPORT = False
    CAP_INSTALL = False
    CAP_LOGIN = False
    CAP_PUSH = False
    CAP_RUN = True  # required by build
    CAP_VERSION = False

    display_name = u'buildah'

    _client = None

    @property
    def ansible_build_args(self):
        """Additional commandline arguments necessary for ansible-playbook runs during build"""
        return '-c buildah'

    @log_runs
    @host_only
    def run_conductor(self, command, config, base_path, params, engine_name=None, volumes=None):
        volumes = volumes or {}
        volumes["/var/lib/containers"] = {
            "bind": "/var/lib/containers",
            "mode": "rw"
        }
        volumes[base_path] = {'bind': '/src', 'mode': "rw"}

        # FIXME: DOCKER_HOST env var
        volumes['/var/run/docker.sock'] = {'bind': '/var/run/docker.sock',
                                           'mode': 'rw'}

        if not engine_name:
            engine_name = __name__.rsplit('.', 2)[-2]
        return super(Engine, self).run_conductor(command, config, base_path, params,
                                                 engine_name=engine_name,
                                                 volumes=volumes)

    @log_runs
    def container_name_for_service(self, service_name):
        return u'%s_%s' % (self.project_name, service_name)

    @log_runs
    def get_container_id_for_service(self, service_name):
        if ENV == "conductor":
            j = subprocess.check_output(["buildah", "containers", "--json"])
            containers = json.loads(j)
            f = self.container_name_for_service(service_name)
            matched = [x for x in containers if x["containername"] == f]
            if len(matched) == 1:
                return matched[0]["id"]
            elif len(matched) > 1:
                raise Exception()
            else:
                return None
        else:  # host
            super(Engine, self).get_container_id_for_service(service_name)

    @log_runs
    def get_image_id_by_tag(self, tag):
        if ENV == "conductor":
            j = subprocess.check_output(["buildah", "images", "--json"])
            images = json.loads(j)
            matched = [x for x in images if tag in x["names"]]
            if len(matched) == 1:
                return matched[0]["id"]
            elif len(matched) > 1:
                raise Exception()
            else:
                return None
        else:  # host
            super(Engine, self).get_image_id_by_tag(tag)

    @log_runs
    def get_image_name_for_image_id(self, image_id):
        j = subprocess.check_output(["buildah", "images", "--json"])
        images = json.loads(j)
        matched = [x for x in images if image_id == x["id"]]
        if len(matched) == 1:
            return matched[0]["names"][0]
        else:
            raise Exception()

    @log_runs
    def run_container(self, image_id, service_name, **kwargs):
        if ENV == "conductor":
            cont_name = kwargs.get("name", service_name)
            image_name = self.get_image_name_for_image_id(image_id)
            subprocess.check_call([
                "buildah",
                "from",
                "--name", cont_name,
                image_name,
            ])
            config_cmd = ["buildah", "config"]
            try:
                config_cmd += ["--workingdir", kwargs["working_dir"]]
            except KeyError:
                pass
            for k, v in kwargs["environment"].items():
                config_cmd += ["-e", k, v]
            subprocess.check_call(config_cmd + [cont_name])
            # TODO: volumes during run
        else:  # host
            super(Engine, self).run_container(image_id, service_name, **kwargs)

    @log_runs
    def image_name_for_service(self, service_name):
        if ENV == "conductor":
            return u'%s-%s' % (self.project_name.lower(), service_name.lower())
        else:  # host
            super(Engine, self).image_name_for_service(service_name)

    @log_runs
    def get_latest_image_id_for_service(self, service_name):
        if ENV == "conductor":
            j = subprocess.check_output(["buildah", "images", "--json"])
            images = json.loads(j)
            f = self.image_name_for_service(service_name)
            matched = [x for x in images if f in x["names"]]
            if len(matched) == 1:
                return matched[0]["id"]
            elif len(matched) > 1:
                raise Exception()
            else:
                return None
        else:  # host
            super(Engine, self).get_latest_image_id_for_service(service_name)

    def service_is_running(self, service):
        """
        buildah containers are never running; when it exists,
        it means it's running and we should either clean or use
        """
        if ENV == "conductor":
            return self.get_container_id_for_service(service)
        else:  # host
            super(Engine, self).service_is_running(service)
