# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)


class BaseShipItEngine(object):
    name = None

    def __init__(self, base_path):
        self.base_path = base_path

    def add_options(self, subparser):
        """
        Given an argument subparser, add to it the arguments and options
        this engine allows.

        https://docs.python.org/2/library/argparse.html#sub-commands

        :param subparser: An argparse.ArgumentSubparser
        :return: None
        """
        raise NotImplementedError()

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
        :return: string: name of directory where config was saved
        """
        raise NotImplementedError()
