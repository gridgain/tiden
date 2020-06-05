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

from .util import log_print, log_put, print_red, get_cur_timestamp
from .tidenexception import TidenException
from enum import Enum


class TidenPluginException (TidenException):
    pass


class TidenPlugin:

    def __init__(self, name, config, **kwargs):
        self.name = name
        self.config = config
        self.ssh = None
        self.options = self.config['plugins'][name]

    def set(self, **kwargs):
        for name, val in kwargs.items():
            setattr(self, name, val)

    def log_print(self, msg=None, **kwargs):
        if msg is None:
            log_print()
        else:
            log_print("[%s][%s] %s" % (get_cur_timestamp(), self.name, msg), **kwargs)

    def print_red(self, *args, **kwargs):
        print_red(*args, **kwargs)

    def log_put(self, msg, **kwargs):
        log_put("[%s][%s] %s" % (get_cur_timestamp(), self.name, msg), **kwargs)

    def before_prepare_artifacts(self, *args, **kwargs):
        pass

    def after_config_loaded(self, *args, **kwargs):
        return args

    def before_hosts_setup(self, *args, **kwargs):
        pass

    def after_hosts_setup(self, *args, **kwargs):
        pass

    def before_tests_run(self, *args, **kwargs):
        """
        This callback is called once per session before running any tests.
        If it returns False - tests won't be started.
        :param args:
        :param kwargs:
        :return:
        """
        return True

    def before_test_class_setup(self, *args, **kwargs):
        pass

    def after_test_class_setup(self, *args, **kwargs):
        pass

    def before_test_method_setup(self, *args, **kwargs):
        pass

    def before_test_method(self, *args, **kwargs):
        pass

    def after_test_method(self, *args, **kwargs):
        pass

    def after_test_method_setup(self, *args, **kwargs):
        pass

    def before_test_method_teardown(self, *args, **kwargs):
        pass

    def after_test_method_teardown(self, *args, **kwargs):
        pass

    def before_test_class_teardown(self, *args, **kwargs):
        pass

    def after_test_class_teardown(self, *args, **kwargs):
        pass

    def after_tests_run(self, *args, **kwargs):
        pass


class TidenPluginScope(Enum):
    # perform plugin actions once per whole test run
    RUN = 0

    # perform plugin actions per each test class
    CLASS = 1

    # perform plugin actions per each test method
    METHOD = 2

    @classmethod
    def from_options(cls, plugin_name, options, default):
        if options.get('scope'):
            try:
                return TidenPluginScope[options['scope'].upper()]
            except KeyError:
                raise TidenPluginException(
                    'Unknown plugin "%s" scope "%s", use: %s' % (
                        plugin_name, options['scope'], TidenPluginScope.values()))
        else:
            return default

    @classmethod
    def values(cls):
        return ', '.join(list(cls.__members__.keys()))

    def scoped_local_dir(self, config):
        scope = self.value
        if scope == 0:
            return config['suite_var_dir']
        if scope == 1:
            return config['rt']['test_module_dir']
        if scope == 2:
            return config['rt']['test_dir']

        raise TidenPluginException('Unknown local dir for scope: %s' % self.name)

    def scoped_remote_dir(self, config):
        scope = self.value
        if scope == 0:
            return config['remote']['suite_var_dir']
        if scope == 1:
            return config['rt']['remote']['test_module_dir']
        if scope == 2:
            return config['rt']['remote']['test_dir']

        raise TidenPluginException('Unknown remote dir for scope: %s' % self.name)
