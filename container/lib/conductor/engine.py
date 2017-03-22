# -*- coding: utf-8 -*-
from __future__ import absolute_import

from container.common.visibility import getLogger
logger = getLogger(__name__)

class BaseEngine(object):
    """
    Interface class for implementations of various container engine integrations
    into Ansible Container.
    """

    def __init__(self, project_name, services, debug=False, selinux=True,
                 **kwargs):
        self.project_name = project_name
        self.services = services
        self.debug = debug
        self.selinux = selinux

    @property
    def display_name(self):
        return __name__.split('.')[-2].capitalize()

    @property
    def ansible_args(self):
        """Additional commandline arguments necessary for ansible-playbook runs."""
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
    def registry_name(self):
        """Name of the default registry for pushing images"""
        raise NotImplementedError()

    @property
    def auth_config_path(self):
        """Path to config file where the engine stores registry authentication"""
        raise NotImplementedError()

    def run_container(self,
                      image_id,
                      service_name,
                      **kwargs):
        """Run a particular container. The kwargs argument contains individual
        parameter overrides from the service definition."""
        raise NotImplementedError()

    def run_conductor(self, command, config, base_path, params):
        raise NotImplementedError()

    def service_is_running(self, service):
        raise NotImplementedError()

    def service_exit_code(self, service):
        raise NotImplementedError()

    def stop_container(self, container_id, forcefully=False):
        raise NotImplementedError()

    def restart_all_containers(self):
        raise NotImplementedError()

    def inspect_container(self, container_id):
        raise NotImplementedError()

    def delete_container(self, container_id):
        raise NotImplementedError()

    def get_container_id_for_service(self, service_name):
        raise NotImplementedError()

    def get_image_id_by_fingerprint(self, fingerprint):
        raise NotImplementedError()

    def get_image_id_by_tag(self, tag):
        raise NotImplementedError()

    def get_latest_image_id_for_service(self, service_name):
        raise NotImplementedError()

    def commit_role_as_layer(self,
                             container_id,
                             service_name,
                             fingerprint,
                             metadata,
                             with_name=False):
        raise NotImplementedError()

    def tag_image_as_latest(self, service_name, image_id):
        raise NotImplementedError()

    def generate_orchestration_playbook(self, repository_data=None):
        """If repository_data is specified, presume to pull images from that
        repository. If not, presume the images are already present."""
        raise NotImplementedError()

    def push(self, image_id, service_name, repository_data):
        """
        Push an image to a registry.
        """
        raise NotImplementedError()

    def build_conductor_image(self, base_path, base_image, cache=True):
        raise NotImplementedError()

    def get_runtime_volume_id(self):
        """Get the volume ID for the portable python runtime."""
        raise NotImplementedError()

    def import_project(self, base_path, import_from, bundle_files=False, **kwargs):
        raise NotImplementedError()

    def login(self, username, password, email, url, config_path):
        """
        Authenticate with a registry, and update the engine's config file. Otherwise,
        verify there is an existing authentication record within the config file for
        the given url. Returns a username.
        """
        raise NotImplementedError()

    @staticmethod
    def get_registry_username(registry_url, config_path):
        """
        Read authentication data stored at config_path for the regisrtry url, and
        return the username
        """
        raise NotImplementedError()
