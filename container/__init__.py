# -*- coding: utf-8 -*-
from __future__ import absolute_import

__version__ = '0.9.3rc0'

import os
import functools

# Many features of Ansible Container are flagged on whether or not we're running
# inside the Conductor container or not. This is the flag.
ENV = 'conductor' if os.environ.get('ANSIBLE_CONTAINER') else 'host'

def conductor_only(fn):
    @functools.wraps(fn)
    def __wrapped__(*args, **kwargs):
        if ENV != 'conductor':
            raise EnvironmentError('This method can only be run inside of the '
                                   'conductor container.')
        return fn(*args, **kwargs)
    return __wrapped__

def host_only(fn):
    @functools.wraps(fn)
    def __wrapped__(*args, **kwargs):
        if ENV != 'host':
            raise EnvironmentError('This method can only be run outside of the '
                                   'conductor container.')
        return fn(*args, **kwargs)
    return __wrapped__
