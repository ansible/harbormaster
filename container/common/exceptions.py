# -*- coding: utf-8 -*-
from __future__ import absolute_import

from container.common.visibility import getLogger
logger = getLogger(__name__)


class AnsibleContainerException(Exception):
    pass

class AnsibleContainerConductorException(Exception):
    pass

class AnsibleContainerNotInitializedException(AnsibleContainerException):
    pass

class AnsibleContainerAlreadyInitializedException(AnsibleContainerException):
    pass

class AnsibleContainerNoAuthenticationProvidedException(AnsibleContainerException):
    pass

class AnsibleContainrRolesPathCreationException(AnsibleContainerException):
    pass

class AnsibleContainerDockerConfigFileException(AnsibleContainerException):
    pass

class AnsibleContainerDockerLoginException(AnsibleContainerException):
    pass

class AnsibleContainerConfigException(AnsibleContainerException):
    pass

class AnsibleContainerRegistryNotFoundException(AnsibleContainerException):
    pass

class AnsibleContainerRegistryAttributeException(AnsibleContainerException):
    pass

class AnsibleContainerMissingRegistryName(AnsibleContainerException):
    pass

class AnsibleContainerNoMatchingHosts(AnsibleContainerException):
    pass

class AnsibleContainerHostNotTouchedByPlaybook(AnsibleContainerException):
    pass

class AnsibleContainerShipItException(AnsibleContainerException):

    def __init__(self, msg, stdout=None, stderr=None):
        self.stderr = stderr
        self.stdout = stdout

        Exception.__init__(self, msg)

class AnsibleContainerFilterException(AnsibleContainerException):
    pass

class AnsibleContainerMissingPersistentVolumeClaim(AnsibleContainerException):
    pass

class AnsibleContainerListHostsException(AnsibleContainerException):
    pass


