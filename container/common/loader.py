# -*- coding: utf-8 -*-
from __future__ import absolute_import

import importlib

from container.common.visibility import getLogger
logger = getLogger(__name__)

from .utils import CAPABILITIES

# If "conductor" is a thing, we're inside of a container. If not, we're not.
try:
    import conductor
except ImportError:
    package = 'container'
else:
    package = 'conductor'
logger.info('Engine loader looking in %s for engines', package)

def load_engine(capabilities_needed, engine_name, project_name,
                services=[], **kwargs):
    logger.debug(u"Loading engine capabilities", capabilities=capabilities_needed, engine=engine_name)
    mod = importlib.import_module('%s.%s.engine' % (package, engine_name))
    engine_obj = mod.Engine(project_name, services, **kwargs)
    for capability in capabilities_needed:
        if not getattr(engine_obj, 'CAP_%s' % capability):
            raise ValueError(u'The engine for %s does not support %s',
                             engine_obj.display_name,
                             CAPABILITIES[capability])
    return engine_obj
