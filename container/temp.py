# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)


import tempfile
import shutil
import os

class MakeTempDir(object):
    temp_dir = None

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp()
        logger.debug('Using temporary directory %r...', self.temp_dir)
        return os.path.realpath(self.temp_dir)

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            logger.debug('Cleaning up temporary directory %r...', self.temp_dir)
            shutil.rmtree(self.temp_dir)
        except Exception:
            logger.exception('Failure cleaning up temp space %r', self.temp_dir)
