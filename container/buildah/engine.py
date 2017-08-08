# -*- coding: utf-8 -*-
from __future__ import absolute_import

import json
import subprocess

try:
    import httplib as StatusCodes
except ImportError:
    from http import HTTPStatus as StatusCodes

from container.engine import BaseEngine
from container.utils.visibility import getLogger
from container import exceptions


logger = getLogger(__name__)


def create_buildah_container(container_image, container_name=None, working_dir=None,
                             env_vars=None):
    cmd = ["buildah", "from", "--name", container_name, container_image]
    subprocess.check_call(cmd)

    config_args = []
    if working_dir:
        config_args += ["--workingdir", working_dir]
    if env_vars:
        for k, v in env_vars.items():
            config_args += ["-e", k, v]
    if config_args:
        # TODO: bind-mounts are configured via run command
        config_cmd = ["buildah", "config"] + config_args + [container_name]
        subprocess.check_call(config_cmd)

    return container_name


# got to be named 'Engine'
class Engine(BaseEngine):

    # Capabilities of engine implementations
    CAP_BUILD_CONDUCTOR = False
    CAP_BUILD = False
    CAP_DEPLOY = False
    CAP_IMPORT = False
    CAP_INSTALL = False
    CAP_LOGIN = False
    CAP_PUSH = False
    CAP_RUN = True  # required by build
    CAP_VERSION = False

    display_name = u'buildah'

    @property
    def ansible_build_args(self):
        """Additional commandline arguments necessary for ansible-playbook runs during build"""
        return '--connection=buildah'

    def container_name_for_service(self, service_name):
        return u'%s_%s' % (self.project_name, service_name)

    def get_container_id_for_service(self, service_name):
        """ list available buildah containers and get the selected one """
        j = subprocess.check_output(["buildah", "containers", "--json"])
        containers = json.loads(j)
        f = self.container_name_for_service(service_name)
        matched = [x for x in containers if x["containername"] == f]
        if len(matched) == 1:
            return matched[0]["id"]
        elif len(matched) > 1:
            raise exceptions.AnsibleContainerException(
                "Container for service %s not found." % service_name)
        else:
            return None

    # def get_image_id_by_tag(self, tag):
    #     if ENV == "conductor":
    #         j = subprocess.check_output(["buildah", "images", "--json"])
    #         images = json.loads(j)
    #         matched = [x for x in images if tag in x["names"]]
    #         if len(matched) == 1:
    #             return matched[0]["id"]
    #         elif len(matched) > 1:
    #             raise Exception()
    #         else:
    #             return None
    #     else:  # host
    #         super(Engine, self).get_image_id_by_tag(tag)

    def get_image_name_for_image_id(self, image_id):
        j = subprocess.check_output(["buildah", "images", "--json"])
        images = json.loads(j)
        matched = [x for x in images if image_id == x["id"]]
        if len(matched) == 1:
            return matched[0]["names"][0]
        else:
            raise Exception()

    def run_container(self, image_id, service_name, **kwargs):
        cont_name = kwargs.get("name", self.get_container_name_for_service(service_name))
        working_dir = kwargs.get("working_dir", None)
        env_vars = kwargs.get("environment", {})
        image_name = self.get_image_name_for_image_id(image_id)

        container_name = create_buildah_container(
            image_name, cont_name, working_dir=working_dir, env_vars=env_vars)

        command = kwargs["command"]
        subprocess.check_call(["buildah", "run", "--", container_name] + command)

    def image_name_for_service(self, service_name):
        if service_name == 'conductor' or self.services[service_name].get('roles'):
            return u'%s-%s' % (self.project_name.lower(), service_name.lower())
        else:
            return self.services[service_name].get('from')

    def get_latest_image_id_for_service(self, service_name):
        """ list all buildah images and get the one tagged for selected service name """
        j = subprocess.check_output(["buildah", "images", "--json"])
        images = json.loads(j)  # FIXME: raise sensible exc
        f = self.image_name_for_service(service_name)
        matched = [x for x in images if f in x["names"]]
        if len(matched) == 1:
            return matched[0]["id"]
        elif len(matched) > 1:
            raise exceptions.AnsibleContainerException(
                "Image for service %s not found." % service_name)
        else:
            return None

    def service_is_running(self, service):
        """
        buildah containers are never running; when it exists,
        it means it's running and we should either clean or use
        """
        return self.get_container_id_for_service(service)

    def stop_container(self, container_id, forcefully=False):
        """
        there is no stop operation for buildah containers
        """
        pass

    def delete_container(self, container_id, remove_volumes=False):
        # TODO: figure out volumes
        subprocess.check_call(["buildah", "rm", container_id])

    def await_conductor_command(self, command, config, base_path, params, save_container=False):
        raise NotImplementedError("we need to figure this out")
