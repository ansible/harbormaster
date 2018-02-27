# -*- coding: utf-8 -*-
# This is a copy of /container/visibility.py copied for accessibility inside
# the conductor
from __future__ import absolute_import

import inspect
import logging
import sys
import json
from io import StringIO

from ._text import to_text

from ruamel.yaml.compat import ordereddict

from structlog import wrap_logger
from structlog.dev import ConsoleRenderer
from structlog.stdlib import filter_by_level, add_logger_name
from structlog.stdlib import BoundLogger, PositionalArgumentsFormatter
from structlog.processors import format_exc_info, TimeStamper

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format='%(message)s',
)

def local_var_info(logger, call_name, event_dict):
    if logger.getEffectiveLevel() > logging.DEBUG or call_name != 'debug':
        return event_dict
    caller = inspect.stack()[5]
    event_dict.update({
        'locals': caller[0].f_locals,
    })
    return event_dict

def unorder_dict(logger, call_name, event_dict):
    if logger.getEffectiveLevel() > logging.DEBUG:
        return event_dict
    for key, value in event_dict.items():
        if isinstance(value, ordereddict):
            event_dict[key] = json.dumps(value)
    return event_dict

def add_caller_info(logger, call_name, event_dict):
    if logger.getEffectiveLevel() > logging.DEBUG:
        return event_dict
    elif event_dict.get('terse'):
        event_dict.pop('terse')
        return event_dict
    caller = inspect.stack()[5]

    if 'caller_func' not in event_dict:
        event_dict['caller_func'] = caller[0].f_code.co_name
    if 'caller_file' not in event_dict:
        event_dict['caller_file'] = caller[1]
    if 'caller_line' not in event_dict:
        event_dict['caller_line'] = caller[2]

    return event_dict

def info_formatter(_, call_name, event_dict):
    sio = StringIO()
    for dont_care in ('timestamp', 'logger', 'level'):
        event_dict.pop(dont_care, None)

    if call_name not in ('info', 'debug', 'notset'):
        sio.write(to_text(call_name.upper()))
        sio.write(u'\t')

    sio.write(to_text(event_dict.pop('event')))
    sio.write(u'\t')

    # make sure we don't put multiline exceptions in regular k/v
    exc = event_dict.pop('exception', None)

    sio.write(
        u' '.join(
            u'{0}={1}'.format(k, event_dict[k])
            for k in sorted(event_dict.keys())
        )
    )

    if exc is not None:
        sio.write(u'\n' + exc)

    return sio.getvalue()

def alternate_dev_formatter():
    debugging = ConsoleRenderer()
    def with_memoized_loggers(logger, call_name, event_dict):
        if logger.getEffectiveLevel() > logging.DEBUG:
            return info_formatter(logger, call_name, event_dict)
        return debugging(logger, call_name, event_dict)
    return with_memoized_loggers

def getLogger(name):
    return wrap_logger(
        logging.getLogger(name),
        processors=[
            filter_by_level,
            add_logger_name,
            add_caller_info,
            #local_var_info,
            unorder_dict,
            TimeStamper(fmt="ISO", utc=False),
            format_exc_info,
            PositionalArgumentsFormatter(),
            alternate_dev_formatter()
        ],
        wrapper_class=BoundLogger,
    )
