# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
import os

logger = logging.getLogger(__name__)


from .constants import SHIPIT_PATH, SHIPIT_CONFIG_PATH
from ..exceptions import AnsibleContainerShipItException


def create_config_output_path(base_dir, engine_name):
    dest_path = os.path.join(base_dir, SHIPIT_PATH, SHIPIT_CONFIG_PATH, engine_name)
    try:
        os.makedirs(dest_path)
    except OSError:
        # ignore if path already exists
        pass
    except Exception as exc:
        raise AnsibleContainerShipItException("Error creating %s - %s" % (dest_path, str(exc)))
    return dest_path
