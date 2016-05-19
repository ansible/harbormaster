# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

class AnsibleContainerNotInitializedException(Exception):
    pass


class AnsibleContainerAlreadyInitializedException(Exception):
    pass

class AnsibleContainerNoAuthenticationProvided(Exception):
    pass
