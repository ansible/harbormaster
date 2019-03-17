# -*- coding: utf-8 -*-
from __future__ import absolute_import

__version__ = '0.9.3rc4'

import os
import sys
import functools

# Many features of Ansible Container are flagged on whether or not we're running
# inside the Conductor container or not. This is the flag.
ENV = 'conductor' if os.environ.get('ANSIBLE_CONTAINER') else 'host'
REMOTE_DEBUGGING = True if os.environ.get('REMOTE_DEBUGGING') else False

if ENV != 'host' and REMOTE_DEBUGGING:
    print("Checking for debugging capabilities...")
    try:
        sys.path.append('/_ansible/build/pycharm-debug.egg')
        print("import pydevd && set trace 172.17.0.1 55507")
        import pydevd
        # 172.17.0.1 host.docker.internal
        pydevd.settrace('172.17.0.1', port=55507, stdoutToServer=True, stderrToServer=True)
    except ImportError:
        pass
    except Exception:
        pass


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
