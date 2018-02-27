# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .utils.visibility import getLogger
logger = getLogger(__name__)


class AnsibleContainerException(Exception):
    pass

class AnsibleContainerConductorException(AnsibleContainerException):
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

class AnsibleContainerDockerConnectionRefused(AnsibleContainerException):
    pass

class AnsibleContainerDockerConnectionAborted(AnsibleContainerException):
    pass

class AnsibleContainerConfigException(AnsibleContainerException):
    pass

class AnsibleContainerRegistryNotFoundException(AnsibleContainerException):
    pass

class AnsibleContainerRegistryAttributeException(AnsibleContainerException):
    pass

class AnsibleContainerMissingImage(AnsibleContainerException):
    pass

class AnsibleContainerMissingRegistryName(AnsibleContainerException):
    pass

class AnsibleContainerNoMatchingHosts(AnsibleContainerException):
    pass

class AnsibleContainerHostNotTouchedByPlaybook(AnsibleContainerException):
    pass

class AnsibleContainerDeployException(AnsibleContainerException):
    pass

class AnsibleContainerFilterException(AnsibleContainerException):
    pass

class AnsibleContainerMissingPersistentVolumeClaim(AnsibleContainerException):
    pass

class AnsibleContainerListHostsException(AnsibleContainerException):
    pass

class AnsibleContainerEngineCapability(AnsibleContainerException):
    pass

class AnsibleContainerGalaxyFatalException(AnsibleContainerException):
    pass

class AnsibleContainerGalaxyRoleException(AnsibleContainerException):
    pass

class AnsibleContainerImportDirDockerException(AnsibleContainerException):
    pass

class AnsibleContainerImportExistsException(AnsibleContainerException):
    pass

class AnsibleContainerRequestException(AnsibleContainerException):
    pass
