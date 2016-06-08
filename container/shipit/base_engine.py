# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)


class BaseShipItEngine(object):

    def __init__(self, base_path):
        self.base_path = base_path

    def run(self, **kwargs):
        """
        Generate an Ansible role and sample playbook to deploy to the target cloud.

        :param kwargs: Commandline options provided at runtime
        :return:
        """
        raise NotImplementedError()

    def save_config(self, kwargs):
        """
        Called when --save-config option True. Generate configuration templates and write to filesystem.

        :param kwargs: Comandline options provided at runtime.
        :return:
        """
        raise NotImplementedError()
