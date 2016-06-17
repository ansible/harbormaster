# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import sys

from StringIO import StringIO
from functools import wraps
from distutils import spawn

from compose.cli import main
from compose.cli.log_printer import LogPrinter, build_log_presenters

__all__ = ['teed_stdout',
           'which_docker',
           'config_to_compose']

# Don't try this at home, kids.

# *sigh* Okay, fine. Well...
# We need to tee the stdout to a StringIO buffer as well as to stdout.
# If you've got a better idea, I'm all ears.

class Tee(StringIO):
    def write(self, x):
        StringIO.write(self, x)
        sys.stdout.write(x)

    def flush(self):
        StringIO.flush(self)
        sys.stdout.flush()


def monkeypatch__log_printer_from_project(buffer):
    @wraps(main.log_printer_from_project)
    def __wrapped__(
            project,
            containers,
            monochrome,
            log_args,
            cascade_stop=False,
            event_stream=None,
    ):
        return LogPrinter(
            containers,
            build_log_presenters(project.service_names, monochrome),
            event_stream or project.events(),
            cascade_stop=cascade_stop,
            output=buffer,
            log_args=log_args)

    return __wrapped__


original__log_printer_from_project = main.log_printer_from_project


class TeedStdout(object):
    stdout = None

    def __enter__(self):
        self.stdout = StringIO()
        main.log_printer_from_project = monkeypatch__log_printer_from_project(self.stdout)
        return self.stdout

    def __exit__(self, exc_type, exc_val, exc_tb):
        main.log_printer_from_project = original__log_printer_from_project

teed_stdout = TeedStdout

# Phew. That sucked.

def which_docker():
    return spawn.find_executable('docker')

def config_to_compose(config, shipit=False):
    # This could probably be better done - include what keys are in compose vs
    # removing the ones that aren't.
    compose = config.get('services', {}).copy()
    for service, service_config in compose.items():
        if 'options' in service_config and not shipit:
            del service_config['options']
        if 'dev_overrides' in service_config and shipit:
            del service_config['dev_overrides']
    logger.debug('Compose derived from config:')
    logger.debug(unicode(compose))
    return compose
