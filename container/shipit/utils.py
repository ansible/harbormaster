# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
import os
import subprocess
import shlex
import select

logger = logging.getLogger(__name__)


from ..exceptions import AnsibleContainerShipItException


def create_path(path):
    try:
        os.makedirs(path)
    except OSError:
        pass
    except Exception as exc:
        raise AnsibleContainerShipItException("Error creating %s - %s" % (path, str(exc)))

def run_command(args):
    '''
    Execute a command, returns rc, stdout, and stderr.

    :param args: Command to execute.
    '''

    if isinstance(args, basestring):
        if isinstance(args, unicode):
            args = args.encode('utf-8')
        args = shlex.split(args)
    else:
        raise AnsibleContainerShipItException("Argument 'args' to run_command must be list or string")

    args = [os.path.expandvars(os.path.expanduser(x)) for x in args if x is not None]

    st_in = None

    # Clean out python paths set by ziploader
    if 'PYTHONPATH' in os.environ:
        pypaths = os.environ['PYTHONPATH'].split(':')
        pypaths = [x for x in pypaths \
                    if not x.endswith('/ansible_modlib.zip') \
                    and not x.endswith('/debug_dir')]
        os.environ['PYTHONPATH'] = ':'.join(pypaths)

    kwargs = dict(
        executable=None,
        shell=False,
        close_fds=True,
        stdin=st_in,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # store the pwd
    prev_dir = os.getcwd()

    try:
        cmd = subprocess.Popen(args, **kwargs)
        stdout = ''
        stderr = ''
        rpipes = [cmd.stdout, cmd.stderr]
        while True:
            rfd, wfd, efd = select.select(rpipes, [], rpipes, 1)
            if cmd.stdout in rfd:
                dat = os.read(cmd.stdout.fileno(), 9000)
                stdout += dat
                if dat == '':
                    rpipes.remove(cmd.stdout)
            if cmd.stderr in rfd:
                dat = os.read(cmd.stderr.fileno(), 9000)
                stderr += dat
                if dat == '':
                    rpipes.remove(cmd.stderr)
            # only break out if no pipes are left to read or
            # the pipes are completely read and
            # the process is terminated
            if (not rpipes or not rfd) and cmd.poll() is not None:
                break
            # No pipes are left to read but process is not yet terminated
            # Only then it is safe to wait for the process to be finished
            # NOTE: Actually cmd.poll() is always None here if rpipes is empty
            elif not rpipes and cmd.poll() is not None:
                cmd.wait()
                # The process is terminated. Since no pipes to read from are
                # left, there is no need to call select() again.
                break
        cmd.stdout.close()
        cmd.stderr.close()
        rc = cmd.returncode
    except Exception:
        raise

    os.chdir(prev_dir)
    return rc, stdout, stderr
