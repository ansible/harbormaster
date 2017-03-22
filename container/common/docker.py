# -*- coding: utf-8 -*-
from __future__ import absolute_import

from ..common.visibility import getLogger
logger = getLogger(__name__)

try:
    import docker
    from docker import errors as docker_errors
except ImportError, e:
    logger.debug('Import error: %s', e)
    raise ImportError('Use of this engine requires you "pip install \'docker>=2.1\'" first.')

from . import exceptions

class DockerEngineUtilityMixin(object):
    FINGERPRINT_LABEL_KEY = 'com.ansible.container.fingerprint'
    LAYER_COMMENT = 'Built with Ansible Container (https://github.com/ansible/ansible-container)'
    display_name = u'Docker\u2122 daemon'

    _client = None
    _api_client = None

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

    def container_name_for_service(self, service_name):
        return u'%s_%s' % (self.project_name, service_name)

    def image_name_for_service(self, service_name):
        return u'%s-%s' % (self.project_name, service_name)

    def get_container_id_for_service(self, service_name):
        try:
            container = self.client.containers.get(self.container_name_for_service(service_name))
        except docker_errors.NotFound:
            return None
        else:
            return container.id

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
