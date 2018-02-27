# -*- coding: utf-8 -*-
from __future__ import absolute_import

from container.utils.visibility import getLogger
logger = getLogger(__name__)

from container import host_only, conductor_only

CAPABILITIES = dict(
    BUILD='building container images',
    BUILD_CONDUCTOR='building the Conductor image',
    DEPLOY='pushing and orchestrating containers remotely',
    IMPORT='importing as Ansible Container project',
    LOGIN='authenticate with registry',
    PUSH='push images to registry',
    RUN='orchestrating containers locally',
 )

class BaseEngine(object):
    """
    Interface class for implementations of various container engine integrations
    into Ansible Container.
    """

    # Capabilities of engine implementations
    CAP_BUILD_CONDUCTOR = False
    CAP_BUILD = False
    CAP_DEPLOY = False
    CAP_IMPORT = False
    CAP_INSTALL = False
    CAP_LOGIN = False
    CAP_PUSH = False
    CAP_RUN = False
    CAP_VERSION = False
    CAP_SIM_SECRETS = False

    def __init__(self, project_name, services, debug=False, selinux=True, devel=False, **kwargs):
        self.project_name = project_name
        self.services = services
        self.debug = debug
        self.devel = devel
        self.selinux = selinux
        self.volumes = kwargs.pop('volume_data', None)
        self.secrets = kwargs.pop('secrets', None)

    @property
    def display_name(self):
        return __name__.split('.')[-2].capitalize()

    @property
    def ansible_build_args(self):
        """Additional commandline arguments necessary for ansible-playbook runs during build"""
        raise NotImplementedError()

    @property
    def ansible_orchestrate_args(self):
        """Additional commandline arguments necessary for ansible-playbook runs during orchestrate"""
        raise NotImplementedError()

    @property
    def ansible_exec_path(self):
        return u'ansible-playbook'

    @property
    def python_interpreter_path(self):
        return u'/_usr/bin/python'

    @property
    def default_registry_url(self):
        """Default registry for pushing images"""
        raise NotImplementedError()

    @property
    def default_registry_name(self):
        """Default registry for pushing images"""
        raise NotImplementedError()

    @property
    def registry_name(self):
        """Name of the default registry for pushing images"""
        raise NotImplementedError()

    @property
    def auth_config_path(self):
        """Path to config file where the engine stores registry authentication"""
        raise NotImplementedError()

    @host_only
    def print_version_info(self):
        raise NotImplementedError()

    @conductor_only
    def run_container(self,
                      image_id,
                      service_name,
                      **kwargs):
        """Run a particular container. The kwargs argument contains individual
        parameter overrides from the service definition."""
        raise NotImplementedError()

    @host_only
    def run_conductor(self, command, config, base_path, params, engine_name=None, volumes=None):
        raise NotImplementedError()

    def await_conductor_command(self, command, config, base_path, params, save_container=False):
        raise NotImplementedError()

    def service_is_running(self, service, container_id=None):
        raise NotImplementedError()

    def service_exit_code(self, service, container_id=None):
        raise NotImplementedError()

    def start_container(self, container_id):
        raise NotImplementedError()

    def stop_container(self, container_id, forcefully=False):
        raise NotImplementedError()

    def restart_all_containers(self):
        raise NotImplementedError()

    def inspect_container(self, container_id):
        raise NotImplementedError()

    def delete_container(self, container_id, remove_volumes=False):
        raise NotImplementedError()

    def get_image_id_for_container_id(self, container_id):
        raise NotImplementedError()

    def get_container_id_by_name(self, name):
        raise NotImplementedError()

    def container_name_for_service(self, service_name):
        raise NotImplementedError()

    def get_container_id_for_service(self, service_name):
        return self.get_container_id_by_name(
            self.container_name_for_service(service_name)
        )

    def get_intermediate_containers_for_servie(self, service_name):
        raise NotImplementedError()

    def get_image_id_by_fingerprint(self, fingerprint):
        raise NotImplementedError()

    def get_fingerprint_for_image_id(self, image_id):
        raise NotImplementedError()

    def get_image_id_by_tag(self, tag):
        raise NotImplementedError()

    def get_image_labels(self, image_id):
        raise NotImplementedError

    @conductor_only
    def pull_image_by_tag(self, image_name):
        raise NotImplementedError

    def get_latest_image_id_for_service(self, service_name):
        raise NotImplementedError()

    def get_image_name_for_service(self, service_name):
        raise NotImplementedError()

    @conductor_only
    def commit_role_as_layer(self,
                             container_id,
                             service_name,
                             fingerprint,
                             role,
                             metadata,
                             with_name=False):
        raise NotImplementedError()

    def tag_image_as_latest(self, service_name, image_id):
        raise NotImplementedError()

    @conductor_only
    def generate_orchestration_playbook(self, url=None, namespace=None, local_images=True):
        """
        Generate an Ansible playbook to orchestrate services.
        :param url: registry URL where images will be pulled from
        :param namespace: registry namespace
        :param local_images: bypass pulling images, and use local copies
        :return: playbook dict
        """
        raise NotImplementedError()

    @conductor_only
    def push(self, image_id, service_name, **kwargs):
        """
        Push an image to a registry.
        """
        raise NotImplementedError()

    @host_only
    def build_conductor_image(self, base_path, base_image, cache=True, environment=[]):
        raise NotImplementedError()

    def get_runtime_volume_id(self, mount_point):
        """Get the volume ID for the portable python runtime."""
        raise NotImplementedError()

    @host_only
    def import_project(self, base_path, import_from, bundle_files=False, **kwargs):
        raise NotImplementedError()

    @conductor_only
    def login(self, username, password, email, url, config_path):
        """
        Authenticate with a registry, and update the engine's config file. Otherwise,
        verify there is an existing authentication record within the config file for
        the given url. Returns a username.
        """
        raise NotImplementedError()

    @staticmethod
    @conductor_only
    def get_registry_username(registry_url, config_path):
        """
        Read authentication data stored at config_path for the regisrtry url, and
        return the username
        """
        raise NotImplementedError()

    @conductor_only
    def pre_deployment_setup(self, **kwargs):
        """
        Perform any setup tasks required prior to writing the Ansible playbook.
        return None
        """
        raise NotImplementedError()
