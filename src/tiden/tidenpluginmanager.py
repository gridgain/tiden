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

from glob import glob
from importlib import machinery, util
from os import path
from re import search
from itertools import chain

from .tidenplugin import TidenPluginException
from .util import log_print
from .tidenfabric import TidenFabric


class PluginManager:

    ignore_modules = [
        'tidenplugin.py'
    ]

    mandatory_constants = [
        'TIDEN_PLUGIN_VERSION'
    ]

    def __init__(self, config):
        self.config = config
        self.plugins = {}
        hook_mgr = TidenFabric().get_hook_mgr()
        self.plugins_paths = list(chain(*hook_mgr.hook.tiden_get_plugins_path()))
        self.__import()

    def set(self, **kwargs):
        for name in self.plugins.keys():
            self.plugins[name]['instance'].set(**kwargs)

    def __import(self):
        """
        Import plugin modules, check versions
        :return:
        """
        configured_plugins = self.config.get('plugins', {}).copy()
        plugin_module_files = self.__find_plugin_modules(configured_plugins)
        self.__initialize_plugins(configured_plugins, plugin_module_files)

    def __initialize_plugins(self, configured_plugins, plugin_module_files):
        # Initialize the plugins
        for class_name in configured_plugins.keys():
            if not plugin_module_files.get(class_name):
                raise TidenPluginException('Python module not found in plugins/* for configured plugin %s' % class_name)
            plugin_file = plugin_module_files[class_name]
            # Load module
            loader = machinery.SourceFileLoader(path.basename(plugin_file)[:-3], plugin_file)
            spec = util.spec_from_loader(loader.name, loader)
            plugin_module = util.module_from_spec(spec)
            loader.exec_module(plugin_module)
            preloaded_plugin_config = {
                'file': plugin_file,
                'class': class_name,
            }
            # Check mandatory constants in a plugin module
            for const in self.mandatory_constants:
                preloaded_plugin_config[const] = getattr(plugin_module, const)
            # Get plugin options from config
            plugin_opts = configured_plugins[class_name]
            # Check version if needed
            if not plugin_opts.get('version') or \
                    plugin_opts['version'] == preloaded_plugin_config['TIDEN_PLUGIN_VERSION']:
                # Get the instance
                preloaded_plugin_config['instance'] \
                    = getattr(plugin_module, class_name)(class_name, self.config)
                self.plugins[class_name] = preloaded_plugin_config
                configured_plugins[class_name]['module'] = plugin_file

    def __find_plugin_modules(self, configured_plugins):
        # Find modules
        plugin_module_files = {}
        for plugins_path in self.plugins_paths:
            for plugin_file in glob(path.join(plugins_path, "*.py")):
                # Ignore Tiden abstract plugin class and itself
                if path.basename(plugin_file) in self.ignore_modules or plugin_file == path.abspath(__file__):
                    continue
                # Scan plugin python files and check that the given class in config
                class_name = None
                with open(plugin_file) as r:
                    content = r.read()
                    m = search(r'\s*class\s*([a-zA-z0-9_]+)\s*\(\s*TidenPlugin\s*\)\s*:\s*\n', content)
                    if m:
                        class_name = m.group(1)
                        if not class_name in configured_plugins.keys():
                            continue
                        else:
                            plugin_module_files[class_name] = plugin_file
        return plugin_module_files

    def do(self, point, *args, **kwargs):
        for name in self.plugins.keys():
            try:
                getattr(self.plugins[name]['instance'], point)(*args, **kwargs)
            # TODO too broad and need to be investigated but now we don't stop tests execution
            except TidenPluginException as e:
                log_print('Plugin %s failed in %s: %s' % (name, point, str(e)), color='red')

    def do_check(self, point, *args, **kwargs):
        check_result = True
        for name in self.plugins.keys():
            try:
                plugin_result = getattr(self.plugins[name]['instance'], point)(*args, **kwargs)
                check_result = check_result and plugin_result
                if not check_result:
                    # first failed plugin skips other plugins
                    break
            except TidenPluginException as e:
                log_print('Plugin %s failed in %s: %s' % (name, point, str(e)), color='red')
        return check_result

    def do_filter(self, point, *args, **kwargs):
        plugin_result = args
        for name in self.plugins.keys():
            try:
                plugin_result = getattr(self.plugins[name]['instance'], point)(*args, **kwargs)
                args = plugin_result
            except TidenPluginException as e:
                log_print('Plugin %s failed in %s: %s' % (name, point, str(e)), color='red')
        return plugin_result

