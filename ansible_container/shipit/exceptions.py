# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)


class ShipItException(Exception):

    def __init__(self, msg, stdout=None, stderr=None):
        self.stderr = stderr
        self.stdout = stdout

        Exception.__init__(self, msg)
