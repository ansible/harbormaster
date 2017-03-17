# -*- coding: utf-8 -*-
from __future__ import absolute_import

import inspect
import logging
import sys

from ruamel import ordereddict

from structlog import wrap_logger
from structlog.processors import JSONRenderer
from structlog.dev import ConsoleRenderer
from structlog.stdlib import filter_by_level
from structlog.processors import format_exc_info, TimeStamper

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format='%(message)s',
)

def local_var_info(logger, call_name, event_dict):
    if logger.getEffectiveLevel() > logging.DEBUG or call_name != 'debug':
        return event_dict
    caller = inspect.stack()[3]
    event_dict.update({
        'locals': caller[0].f_locals,
    })
    return event_dict

def _unroll_odict(od):
    """Takes an ordereddict and rebuilds it as a regular dict

    Only used in DEBUG mode, because logs below DEBUG are encoded
    as JSON anyway."""
    cleaned = {}
    for key, value in od.items():
        if isinstance(value, ordereddict.ordereddict):
            cleaned[key] = _unroll_odict(value)
        else:
            cleaned[key] = value
    return cleaned

def unorder_dict(logger, call_name, event_dict):
    if logger.getEffectiveLevel() > logging.DEBUG:
        return event_dict
    for key, value in event_dict.items():
        if isinstance(value, ordereddict.ordereddict):
            event_dict[key] = _unroll_odict(value)
    return event_dict

def add_caller_info(logger, call_name, event_dict):
    if logger.getEffectiveLevel() > logging.DEBUG:
        return event_dict
    elif event_dict.get('terse'):
        event_dict.pop('terse')
        return event_dict
    caller = inspect.stack()[3]

    if 'caller_func' not in event_dict:
        event_dict['caller_func'] = caller[0].f_code.co_name
    if 'caller_file' not in event_dict:
        event_dict['caller_file'] = caller[1]
    if 'caller_line' not in event_dict:
        event_dict['caller_line'] = caller[2]

    return event_dict

def alternate_dev_formatter():
    debugging = ConsoleRenderer()
    standard = JSONRenderer(sort_keys=True)
    def with_memoized_loggers(logger, call_name, event_dict):
        if logger.getEffectiveLevel() > logging.DEBUG:
            return standard(logger, call_name, event_dict)
        return debugging(logger, call_name, event_dict)
    return with_memoized_loggers

def getLogger(name):
    return wrap_logger(
        logging.getLogger(name),
        processors=[
            filter_by_level,
            add_caller_info,
            #local_var_info,
            unorder_dict,
            TimeStamper(fmt="ISO", utc=False),
            format_exc_info,
            alternate_dev_formatter()
        ]
    )
