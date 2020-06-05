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

from tiden.tidenfabric import TidenFabric
from tiden.tidenpluginmanager import PluginManager
from tiden.tidenplugin import TidenPlugin
from os.path import dirname, abspath, join
from os import getcwd


def test_tiden_hook():
    hook_mgr = TidenFabric().get_hook_mgr()
    plugins_path = hook_mgr.hook.tiden_get_plugins_path()
    assert type(plugins_path) == list
    assert len(plugins_path) == 1
    assert type(plugins_path[0]) == list
    assert len(plugins_path[0]) == 2
    assert plugins_path[0][0] == join(dirname(dirname(abspath(__file__))), 'src', 'tiden', 'plugins')
    assert plugins_path[0][1] == join(getcwd(), 'plugins')
    pm = PluginManager({})
    assert pm.plugins_paths == plugins_path[0]
    assert pm.plugins == {}
    pm = PluginManager({
        'plugins': {
            'DockerCleaner': {}
        }
    })
    assert 'DockerCleaner' in pm.plugins
    plugin = pm.plugins['DockerCleaner']
    assert plugin['file'] == join(dirname(dirname(abspath(__file__))), 'src', 'tiden', 'plugins', 'dockercleaner.py')
    assert plugin['class'] == 'DockerCleaner'
    assert plugin['TIDEN_PLUGIN_VERSION'] == '1.0.0'
    assert isinstance(plugin['instance'], TidenPlugin)

