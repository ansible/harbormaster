# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import json
import subprocess

try:
    import httplib as StatusCodes
except ImportError:
    from http import HTTPStatus as StatusCodes

from container import host_only, ENV
from container.engine import BaseEngine
from container.utils.visibility import getLogger
from container import utils


logger = getLogger(__name__)


FILES_DIR_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        'files'))
PLAYBOOK_PATH = os.path.join(FILES_DIR_PATH, "playbook.yaml")


def run_playbook(playbook_path, inventory_path, ansible_build_args=None, debug=False):
    cmd_args = [
        "ansible-playbook",
        "-vvvvv" if debug else "",
        ansible_build_args,
        "-i %s" % inventory_path,
        playbook_path
    ]
    logger.debug("%s", " ".join(cmd_args))
    subprocess.check_call(cmd_args)


def create_buildah_container(container_image, container_name=None, working_dir=None, env_vars=None):
    cmd = ["buildah", "from"]
    if container_name:
        cmd += ["--name", container_name]
        # TODO: else
    cmd += [container_image]
    subprocess.check_call(cmd)

    config_args = []
    if working_dir:
        config_args += ["--workingdir", working_dir]
    if env_vars:
        for k, v in env_vars.items():
            config_args += ["-e", k, v]
    if config_args:
        # TODO: volumes during run
        config_cmd = ["buildah", "config"] + config_args + [container_name]
        subprocess.check_call(config_cmd)

    # subprocess.check_call(["buildah", "run", "--", container_name, "dnf", "install", "-y", "python2"])
    return container_name


# got to be named 'Engine'
class Engine(BaseEngine):

    # Capabilities of engine implementations
    CAP_BUILD_CONDUCTOR = True
    CAP_BUILD = True
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

    @host_only
    def build_conductor_image(self, base_path, base_image, prebaking=False, cache=True):
        """

        :param base_path: cwd
        :param base_image:
        :param prebaking:
        :param cache:
        :return:
        """
        service_name = "conductor"
        with utils.make_temp_dir() as temp_dir:
            logger.info('building conductor image using buildah engine')
            logger.debug("base_path=%s, base_image=%s", base_path, base_image)
            source_dir = os.path.normpath(base_path)

            container_id = create_buildah_container(
                base_image,
                container_name=self.container_name_for_service(service_name)
            )

            inventory_path = os.path.join(temp_dir, 'hosts')
            with open(inventory_path, 'w') as inv_fd:
                inv_fd.write(
                    '%s ansible_host="%s" ansible_python_interpreter="/usr/bin/python3"\n'
                    % (service_name, container_id)
                )
            import ipdb ; ipdb.set_trace()
            run_playbook(PLAYBOOK_PATH, inventory_path, ansible_build_args=self.ansible_build_args,
                         debug=True)
            logger.info("build is done")
        raise Exception("not implemented yet")

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
            raise Exception()
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
        # FIXME: refactor and utilize create_buildah_container()
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

    def image_name_for_service(self, service_name):
        if service_name == 'conductor' or self.services[service_name].get('roles'):
            return u'%s-%s' % (self.project_name.lower(), service_name.lower())
        else:
            return self.services[service_name].get('from')

    def get_latest_image_id_for_service(self, service_name):
        """ list all buildah images and get the one tagged for selected service name """
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

    def service_is_running(self, service):
        """
        buildah containers are never running; when it exists,
        it means it's running and we should either clean or use
        """
        return self.get_container_id_for_service(service)

    def stop_container(self, container_id, forcefully=False):
        """ there is no stop operation for buildah containers, so we remove them """
        subprocess.check_call(["buildah", "rm", container_id])