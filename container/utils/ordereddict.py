# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

# ruamel.yaml.compat.ordereddict might be a ruamel.ordereddict.ordereddict or not
# but if it isn't, it doesn't take the kwarg relax. This thin wrapper is meant
# to disguise that.

from ruamel.yaml.compat import ordereddict

if not repr(ordereddict) == "<type '_ordereddict.ordereddict'>":
    class WrappedOrderedDict(ordereddict):
        def update(self, *args, **kwargs):
            if 'relax' in kwargs:
                del kwargs['relax']
            return super(WrappedOrderedDict, self).update(*args, **kwargs)
    ordereddict = WrappedOrderedDict

