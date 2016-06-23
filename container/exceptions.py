# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

class AnsibleContainerNotInitializedException(Exception):
    pass


class AnsibleContainerAlreadyInitializedException(Exception):
    pass

class AnsibleContainerNoAuthenticationProvidedException(Exception):
    pass

class AnsibleContainrRolesPathCreationException(Exception):
    pass

class AnsibleContainerDockerConfigFileException(Exception):
    pass

class AnsibleContainerDockerLoginException(Exception):
    pass

class AnsibleContainerConfigException(Exception):
    pass

class AnsibleContainerRegistryNotFoundException(Exception):
    pass

class AnsibleContainerRegistryAttributeException(Exception):
    pass

class AnsibleContainerMissingRegistryName(Exception):
    pass

class AnsibleContainerShipItException(Exception):

    def __init__(self, msg, stdout=None, stderr=None):
        self.stderr = stderr
        self.stdout = stdout

        Exception.__init__(self, msg)
