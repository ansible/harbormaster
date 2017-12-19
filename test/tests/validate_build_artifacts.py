# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import os

import docker

from container.docker.engine import Engine

client = docker.from_env()

def test_build_chain_is_valid():
    # The image we built - e.g. rebuild-foo:latest
    image_name = os.environ.get('IMAGE_NAME')
    service_name = image_name.split(':', 1)[0].replace('-', '_')
    # The base image we built it on - e.g. centos:7
    base_name = os.environ.get('BASE_IMAGE_NAME')
    image = client.images.get(image_name)
    base_image = client.images.get(base_name)
    while True:
        assert image.attrs['Config']['Labels'][Engine.FINGERPRINT_LABEL_KEY], (
            'Image %s did not have a fingerprint' % image.id
        )
        role_name = image.attrs['Config']['Labels'][Engine.ROLE_LABEL_KEY]
        parent_image = client.images.get(image.attrs['Parent'])
        if parent_image.id == base_image.id:
            # We hit the base image. All good!
            break
        parent_fingerprint = parent_image.attrs['Config']['Labels'][Engine.FINGERPRINT_LABEL_KEY]
        # There should be a container instance named with the role used to build the
        # current image and the fingerprint of the image it was built upon
        build_container_name = u'%s-%s-%s' % (
            service_name,
            parent_fingerprint[:8],
            role_name)
        assert client.containers.get(build_container_name), (
            'Could not find intermediate build container %s' % build_container_name)
        image = parent_image








