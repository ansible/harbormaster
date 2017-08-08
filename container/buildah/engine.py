# -*- coding: utf-8 -*-
from __future__ import absolute_import

import base64
import datetime
import os
import json
import shutil
import subprocess

from container.docker.engine import log_runs
from container.utils import modules_to_install, roles_to_install, ansible_config_exists, \
    ordereddict_to_list

try:
    import httplib as StatusCodes
except ImportError:
    from http import HTTPStatus as StatusCodes

import container
from container import host_only, ENV
from container.engine import BaseEngine
from container.utils.visibility import getLogger
from container import utils


logger = getLogger(__name__)

FILES_DIR_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        'files'))
BUILD_SCRIPT_NAME = "build-local-conductor.sh"
BUILD_SCRIPT_PATH = os.path.join(FILES_DIR_PATH, BUILD_SCRIPT_NAME)
RUNC_SPEC_NAME = "config.json"
RUNC_SPEC_PATH = os.path.join(FILES_DIR_PATH, RUNC_SPEC_NAME)
PLAYBOOK_NAME = "playbook.yaml"
PLAYBOOK_PATH = os.path.join(FILES_DIR_PATH, PLAYBOOK_NAME)


def graceful_get(d, *keys):
    """
    recursively obtain value from nested dict

    :param d: dict
    :param keys:
    :return: value or None
    """
    response = d
    for k in keys:
        try:
            response = response[k]
        except (KeyError, AttributeError, TypeError) as ex:
            logger.error("can't obtain %s: %s", k, ex)
    return response


# FIXME: not used anywhere
def run_playbook(playbook_path, inventory_path, extra_variables=None,
                  ansible_build_args=None, debug=False):
    cmd_args = [
        "ansible-playbook",
        "-vvvvv" if debug else "",
        ansible_build_args,
        "-i %s" % inventory_path,
    ]
    if extra_variables:
        cmd_args += ["--extra-vars"] + \
            [" ".join(
                ["{}={}".format(k, v)
                 for k, v in extra_variables.items()]
            )]
    cmd_args += [playbook_path]
    logger.debug("%s", " ".join(cmd_args))
    subprocess.check_call(cmd_args)


def inspect_resource(resource_id, resource_type):
    # buildah and kpod output different things
    try:
        i = subprocess.check_output(["buildah", "inspect", "-t", resource_type, resource_id])
    except subprocess.CalledProcessError:
        logger.info("no such %s %s", resource_type, resource_id)
        return None
    metadata = json.loads(i)
    return metadata


def get_image_id(container_image):
    metadata = inspect_resource(container_image, "image")
    return graceful_get(metadata, "image-id")


def pull_image(container_image):
    # FIXME: replace with podman
    subprocess.check_call(["kpod", "pull", container_image])
    return get_image_id(container_image)


def create_buildah_container(
        container_image, container_name, working_dir=None, env_vars=None, user=None,
        volumes=None):
    """
    Create new buildah container according to spec.

    :param container_image:
    :param container_name:
    :param working_dir:
    :param env_vars:
    :param user:
    :param volumes: list of str, same as VOLUME in dockerfile, just metadata
    :return:
    """
    args = ["--name", container_name, container_image]
    # will pull the image by default if it's not present in buildah's storage
    buildah("from", args)

    config_args = []
    if working_dir:
        config_args += ["--workingdir", working_dir]
    if env_vars:
        for k, v in env_vars.items():
            config_args += ["-e", "%s=%s" % (k, v)]
    if volumes:
        for v in volumes:
            config_args += ["-v", v]
    if user:
        config_args += ["--user", user]
    if config_args:
        buildah("config", config_args + [container_name])
    return container_name


def buildah(command, args_and_opts):
    command = ["buildah", command] + args_and_opts
    logger.debug("running command: %s", command)
    return subprocess.check_call(command)


def buildah_with_output(command, args_and_opts):
    command = ["buildah", command] + args_and_opts
    logger.debug("running command: %s", command)
    output = subprocess.check_output(command)
    logger.debug("output: %s", output)
    return output


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

    display_name = 'buildah'

    def __init__(self, *args, **kwargs):
        super(Engine, self).__init__(*args, **kwargs)
        # used during build and to run the conductor container using runc
        self.conductor_mount_point = None
        self.conductor_container_name = None

    @property
    def ansible_build_args(self):
        """Additional commandline arguments necessary for ansible-playbook runs during build"""
        return '--connection=buildah'

    @host_only
    def build_conductor_image(self, base_path, base_image, prebaking=False, cache=True,
                                environment=None):
        if prebaking:
            raise RuntimeError("Prebaking is not supported with buildah engine.")
        service_name = "conductor"
        with utils.make_temp_dir(cd_into=True) as temp_dir:
            buildah_base_image_reference = base_image

            logger.info('building local conductor image using buildah engine')
            logger.debug("base_path=%s, buildah_ref_base_image=%s",
                         base_path, buildah_base_image_reference)

            container_name = self.container_name_for_service(service_name)
            # remove, just in case
            self.delete_container(container_name, ignore_failure=True)
            c = create_buildah_container(base_image, container_name, env_vars=environment)
            # use this also as a conductor container
            self.conductor_mount_point = buildah_with_output("mount", [c]).strip().decode("utf-8")

            build_src = os.path.join(temp_dir, "build-src")
            container_src = os.path.join(temp_dir, "container-src")
            os.mkdir(build_src)
            os.mkdir(container_src)

            source_dir = os.path.normpath(base_path)

            for filename in ['ansible.cfg', 'ansible-requirements.txt',
                             'requirements.yml']:
                file_path = os.path.join(source_dir, filename)
                if os.path.exists(file_path):
                    shutil.copy2(file_path, build_src)

            shutil.copy2(BUILD_SCRIPT_PATH, temp_dir)
            build_script_path = os.path.join(temp_dir, BUILD_SCRIPT_NAME)
            with open(build_script_path, "a") as fd:
                if modules_to_install(base_path):
                    fd.write('pip install --no-cache-dir -r /src/build-src/ansible-requirements.txt\n')
                if roles_to_install(base_path):
                    fd.write('ansible-galaxy install -p /etc/ansible/roles -r /src/build-src/requirements.yml\n')
                if ansible_config_exists(base_path):
                    fd.write('cp /src/build-src/ansible.cfg /etc/ansible/ansible.cfg')

            for dirpath, dirnames, filenames in os.walk(temp_dir):
                for f in filenames:
                    logger.debug("%s", os.path.join(dirpath, f))

            volume = "%s:%s" % (temp_dir, "/src")
            command = os.path.join("/src", BUILD_SCRIPT_NAME)
            self.run_command_in_container(container_name, command, volumes=[volume])

        image_name = self.get_image_name_for_service(service_name)
        buildah("commit", [container_name, image_name])
        logger.info("Build is done, BAM!")
        return

    def commit_role_as_layer(self,
                             container_id,
                             service_name,
                             fingerprint,
                             role,
                             metadata,
                             with_name=False):
        image_name = self.image_name_for_service(service_name)
        image_version = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
        fqim = "%s:%s" % (image_name, image_version)
        buildah("commit", [container_id, fqim])
        return self.get_image_id_by_tag(fqim)

    def tag_image_as_latest(self, service_name, image_id):
        new_name = "%s:%s" % (self.image_name_for_service(service_name), "latest")
        buildah("tag", [image_id, new_name])

    def container_name_for_service(self, service_name):
        return u'%s_%s' % (self.project_name, service_name)

    def get_image_name_for_service(self, service_name):
        return u'%s-%s' % (self.project_name.lower(), service_name.lower())

    @log_runs
    def get_container_id_for_service(self, service_name):
        """ list available buildah containers and get the selected one """
        j = subprocess.check_output(["buildah", "containers", "--json"])
        containers = json.loads(j)
        f = self.container_name_for_service(service_name)
        import pprint
        logger.debug(pprint.pformat(containers))
        logger.debug(f)
        matched = [x for x in containers if x["containername"] == f]
        if len(matched) == 1:
            return matched[0]["id"]
        elif len(matched) > 1:
            raise Exception()
        else:
            return None

    def get_runtime_volume_id(self, mount_point):
        logger.debug("get destination of mount point %s", mount_point)
        # TODO: for python interpretter

    def get_image_id_by_tag(self, tag):
        j = subprocess.check_output(["buildah", "images", "--json"])
        images = json.loads(j)
        for image in images:
            names = image.get("names", []) or []
            # buildah prepends docker.io/library/ by default
            if tag.count("/") == 0:
                for n in names:
                    if n.endswith(tag):
                        return image["id"]
            else:
                if tag in names:
                    return image["id"]

    def get_intermediate_containers_for_service(self, service_name):
        container_substring = self.container_name_for_service(service_name)

        j = subprocess.check_output(["buildah", "containers", "--json"])
        containers = json.loads(j)

        for container in containers:
            container_name = container["containername"]
            if container_name.startswith(container_substring) and \
                    container_name != container_substring:
                yield container_name

    def get_image_id_by_fingerprint(self, fingerprint):
        # TODO: TBD
        return

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
        cont_name = kwargs.get("name", self.container_name_for_service(service_name))
        working_dir = kwargs.get("working_dir", None)
        user = kwargs.get("user", None)
        env_vars = kwargs.get("environment", {})
        image_name = self.get_image_name_for_image_id(image_id)
        # TODO: command

        container_id = create_buildah_container(image_name, cont_name, working_dir=working_dir,
                                                env_vars=env_vars, user=user)

        return container_id

    def run_command_in_container(self, container_name, command, volumes=None):
        c = []
        if volumes:
            for v in volumes:
                c += ["--volume", v]
        # "--" does not help here, it's a shell thing
        c += [container_name, command]
        buildah("run", c)

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
        fqsn = "docker.io/library/%s:latest" % f
        matched = [x for x in images if x["names"] and fqsn in x["names"]]
        if len(matched) == 1:
            return matched[0]["id"]
        elif len(matched) > 1:
            raise Exception()  # FIXME
        else:
            return None

    @log_runs
    def pull_image_by_tag(self, image_name):
        """

        :param image_name:
        :return: str, image IO
        """
        return pull_image(image_name)

    @log_runs
    def service_is_running(self, service, container_id=None):
        """
        buildah containers are never running; when it exists,
        it means it's running and we should either clean or use
        """
        logger.debug("service=%s, container_id=%s", service, container_id)
        if container_id:
            result = bool(self.inspect_container(container_id))
        else:
            result = bool(self.get_container_id_for_service(service))
        logger.info("is container for service %s running? %s", service, result)
        return result

    def get_container_id_by_name(self, name):
        return graceful_get(inspect_resource(name, "container"), "container-id")

    def inspect_container(self, container_id):
        return inspect_resource(container_id, "container")

    def start_container(self, container_id):
        """ there is no start operation for buildah containers """
        logger.info("starting buildah container is a noop")
        if not self.inspect_container(container_id):
            raise ValueError("no such container %s", container_id)
        return container_id

    def stop_container(self, container_id, forcefully=False):
        """ there is no stop operation for buildah containers """
        logger.info("stopping buildah container is a noop")
        if not self.inspect_container(container_id):
            raise ValueError("no such container %s", container_id)
        return

    def delete_container(self, container_id, remove_volumes=False, ignore_failure=False):
        try:
            subprocess.check_call(["buildah", "rm", container_id])
        except subprocess.CalledProcessError:
            logger.error("failed to remove container %s", container_id)
            return
            if ignore_failure:
                return
            raise

    @log_runs
    @host_only
    def run_conductor(self, command, config, base_path, params, engine_name=None, volumes=None):
        service_name = "conductor"
        conductor_settings = config.get('settings', {}).get('conductor', {})
        # image = self.get_latest_image_id_for_service(service_name)
        # FIXME: bug in buildah - it is not possible to do 'from' using buildah's image IDs
        fq = "docker.io/library/%s:latest" % self.image_name_for_service(service_name)

        self.conductor_container_name = self.container_name_for_service(service_name)

        # remove conductor if it exists
        if self.inspect_container(self.conductor_container_name):
            self.delete_container(self.conductor_container_name)

        # FIXME: if the conductor was built during this command, reuse it; if it wasn't, recreate it
        c = create_buildah_container(fq, self.conductor_container_name)
        self.conductor_mount_point = buildah_with_output("mount", [c]).strip().decode("utf-8")

        # This dir needs to be persistent b/c runc's container config is being accessed every time
        # we do some runc operation -- nestetization!
        shutil.copy2(RUNC_SPEC_PATH, self.conductor_mount_point)
        config_json = os.path.join(self.conductor_mount_point, RUNC_SPEC_NAME)
        with open(config_json, "r+") as fd:
            r = json.load(fd)

            r["root"]["path"] = self.conductor_mount_point

            if params.get('devel'):
                conductor_path = os.path.dirname(container.__file__)
                logger.debug(u"Binding Ansible Container code at %s into conductor "
                             u"container", conductor_path)
                r["mounts"].append({
                    "destination": "/_ansible/container",
                    "type": "bind",
                    "source": conductor_path,
                    "options": [
                        "ro",  # no need for rw
                        "bind"
                    ]
                })
            r["mounts"].append({
                "destination": "/var/lib/containers",
                "type": "bind",
                "source": "/var/lib/containers",
                "options": [
                    "rw",
                    "bind"
                ]
            })
            r["mounts"].append({
                "destination": "/var/run/containers",
                "type": "bind",
                "source": "/var/run/containers",
                "options": [
                    "rw",
                    "bind"
                ]
            })
            permissions = 'ro' if command != 'install' else 'rw'
            if params.get('src_mount_path'):
                src_path = params['src_mount_path']
            else:
                src_path = base_path
            r["mounts"].append({
                "destination": "/_src",
                "type": "bind",
                "source": src_path,
                "options": [
                    permissions,
                    "bind"
                ]
            })
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
                    r["mounts"].append({
                        "destination": role_path,
                        "type": "bind",
                        "source": role_path,
                        "options": [
                            "ro",
                            "bind"
                        ]
                    })

            environ = r["process"]["env"]
            if conductor_settings.get('environment'):
                if isinstance(conductor_settings['environment'], dict):
                    environ += ["%s=%s" % (k, v)
                                for k, v in conductor_settings['environment'].items()]
                if isinstance(conductor_settings['environment'], list):
                    environ += conductor_settings['environment']

            if roles_path:
                environ.append("ANSIBLE_ROLES_PATH=%s:/src/roles:/etc/ansible/roles" %
                               ':'.join(expanded_roles_path))
            else:
                environ.append("ANSIBLE_ROLES_PATH=/src/roles:/etc/ansible/roles")

            logger.debug("environment variables = %s", environ)

            fd.seek(0)
            fd.truncate()
            json.dump(r, fd)

        # clean up existing conductor
        subprocess.call(["runc", "delete", "-f", self.conductor_container_name])
        subprocess.check_call(["runc", "run", "--bundle", self.conductor_mount_point,
                               "--detach", self.conductor_container_name])

        serialized_params = base64.b64encode(json.dumps(params).encode("utf-8")).decode()
        serialized_config = base64.b64encode(json.dumps(ordereddict_to_list(config)).encode("utf-8")).decode()

        c = [
            'conductor',
            command,
            '--project-name', self.project_name,
            '--engine', self.display_name,
            '--config', "TBD",
            '--params', serialized_params,
            '--config', serialized_config,
            '--encoding', 'b64json'
        ]
        try:
            subprocess.check_call(["runc", "exec", self.conductor_container_name] + c)
        except subprocess.CalledProcessError:
            logger.error("error while running conductor")
            # subprocess.check_call(["runc", "kill", self.conductor_container_name, "SIGKILL"])
            # subprocess.check_call(["runc", "delete", self.conductor_container_name])
            raise
            # FIXME: if debug, leave container for inspection

    def await_conductor_command(self, command, config, base_path, params, save_container=False):
        logger.debug("running conductor command %s", command)
        self.run_conductor(command, config, base_path, params)
        # TODO: cleanup
