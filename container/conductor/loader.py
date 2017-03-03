# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
import importlib

from .engine import CAPABILITIES

logger = logging.getLogger(__name__)


def load_engine(capabilities_needed, engine_name, project_name, services=[], **kwargs):
    logger.debug(u"Loading capabilities %s for engine %s", ','.join(capabilities_needed), engine_name)
    conductor_module_name = __name__.rsplit('.', 1)[0]
    mod = importlib.import_module('.%s.engine' % engine_name,
                                  package=conductor_module_name)
    engine_obj = mod.Engine(project_name, services, **kwargs)
    for capability in capabilities_needed:
        if not getattr(engine_obj, 'CAP_%s' % capability):
            raise ValueError(u'The engine for %s does not support %s',
                             engine_obj.display_name,
                             CAPABILITIES[capability])
    return engine_obj
