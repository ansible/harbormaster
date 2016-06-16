# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

from ..base_role import BaseShipItRole
from .service import Service
from .deployment import Deployment


class ShipItRole(BaseShipItRole):

    def _get_tasks(self):
        tasks = []
        tasks += Service(config=self.config, project_name=self.project_name).get_task()
        tasks += Deployment(config=self.config, project_name=self.project_name).get_task()
        return tasks
