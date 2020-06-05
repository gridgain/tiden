#!/usr/bin/env python3
#
# Copyright 2017-2020 GridGain Systems.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from datetime import datetime
from sys import stdout
from threading import Thread, current_thread
from copy import deepcopy
from logging import Formatter, Logger, Filter, NOTSET
import logging
import sys

from .tidenexception import TidenException

_loggers = {}


def get_logger(name):
    """
    :return: logger by name if non exist -> create
    :rtype: TidenLogger
    """
    if not isinstance(name, str):
        raise TidenException('Name should be string when get logger')

    try:
        if name not in _loggers:
            new_logger = TidenLogger(name)
            new_logger.set_suite(name)
            _loggers[name] = new_logger
        else:
            _loggers.get(name).add_handlers()

    except Exception as e:
        raise TidenException('Error on logger creating. Message: {}'.format(str(e)))

    return _loggers.get(name, None)


class TidenLoggerFilter(Filter):
    suite_name = '[tiden-core]'
    test_name = ''

    def filter(self, record):
        record.suite_name = self.suite_name
        record.test_name = self.test_name

        return True


class TidenLogger(Logger):
    """Tiden logging implementation"""

    env_config = None
    default_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(suite_name)s%(test_name)s %(message)s')

    def __init__(self, name, level=NOTSET):
        super().__init__(name, level=level)

        self.addFilter(TidenLoggerFilter())
        self.add_handlers()

        if name not in _loggers:
            _loggers[name] = self

    def add_handlers(self):

        if TidenLogger.env_config and not self.handlers:
            config = TidenLogger.env_config
            for handler in config.keys():
                if handler == 'console':
                    _hdr = logging.StreamHandler(sys.stdout)
                    _hdr.setFormatter(logging.Formatter('%(message)s', '%H:%M:%S'))
                if handler == 'file_handler':
                    _hdr = logging.FileHandler(config.get('file_handler').get('log_file'))
                    _hdr.setFormatter(self.default_formatter)

                _hdr.setLevel(logging._nameToLevel.get(config[handler].get('log_level', 'INFO')))
                self.addHandler(_hdr)

    def info(self, msg, *args, **kwargs):
        skip_newline = kwargs.pop('skip_newline', False)
        skip_prefix = kwargs.pop('skip_prefix', False)
        rewrite = kwargs.pop('rewrite', False)

        if skip_newline:
            hdlrs_terminators = [deepcopy(hdlr.terminator) for hdlr in self.handlers]

            for hdlr in self.handlers:
                hdlr.terminator = ""

        if skip_prefix or rewrite:
            hdlrs_formatters = [deepcopy(hdlr.formatter) for hdlr in self.handlers]

            for hdlr in self.handlers:
                if rewrite and skip_prefix:
                    hdlr.setFormatter(Formatter('\r%(message)s'))
                    continue
                if rewrite and not skip_prefix:
                    hdlr.setFormatter(Formatter('\r{}'.format(hdlr.formatter._fmt)))
                    continue
                if not rewrite and skip_prefix:
                    hdlr.setFormatter(Formatter('%(message)s'))

        _colors = dict(black=30, red=31, green=32, yellow=33,
                       blue=34, magenta=35, cyan=36, white=37)
        color_fmt_str = '\x1b[%s;1m%s\x1b[0m'
        color = kwargs.pop('color', False)
        if color:
            msg = color_fmt_str % (_colors.get(color), msg)

        super(TidenLogger, self).info(msg, *args, **kwargs)

        if skip_newline:
            for i in range(len(hdlrs_terminators)):
                self.handlers[i].terminator = hdlrs_terminators[i]

        if skip_prefix or rewrite:
            for i in range(len(hdlrs_formatters)):

                self.handlers[i].setFormatter(hdlrs_formatters[i])

    def set_suite(self, name):
        """Set logger suite name"""

        if not isinstance(name, str):
            raise TidenException('Suite name should be string for logger')

        self.__set_filter_attr('suite_name', name)

    def set_test(self, name):
        """Set logger test name"""

        if not isinstance(name, str):
            raise TidenException('Test name should be string for logger')

        self.__set_filter_attr('test_name', name)

    def __set_filter_attr(self, _attr, _value):
        for filter_ in self.filters:
            if isinstance(filter_, TidenLoggerFilter):
                setattr(filter_, _attr, _value)

    @staticmethod
    def set_logger_env_config(config):
        TidenLogger.env_config = config

    def get_logger_env_config(self):
        return self.env_config

