# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .common.visibility import getLogger
logger = getLogger(__name__)

"""
This engine class is for building/launching the conductor container only.
All other engine functions are in the Conductor class.
"""

class BaseEngine(object):
    # Capabilities of engine implementations
    CAP_BUILD_CONDUCTOR = False
    CAP_BUILD = False
    CAP_DEPLOY = False
    CAP_IMPORT = False
    CAP_LOGIN = False
    CAP_PUSH = False
    CAP_RUN = False

    def __init__(self, project_name, services, debug=False, selinux=True,
                 **kwargs):
        self.project_name = project_name
        self.services = services
        self.debug = debug
        self.selinux = selinux

    def run_conductor(self, command, config, base_path, params):
        raise NotImplementedError()
