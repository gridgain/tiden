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

import os.path
import sys
from importlib import import_module
from math import floor, sqrt
from os import cpu_count

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))


def check_runtests_protocol(module_name, short_name, _config=None):
    """
    Check run-tests.py communication protocol with test module:
    1. module must be importable
    2. module must have test class attribute equal to CamelCased module name
    3. test class must be instantiable with (config, ssh_pool)
    4. test_class must have 'setup' and 'teardown' function attributes
    :return:
    """
    ssh_pool = object()
    config = {}
    if _config is not None:
        config.update(_config)
    module = import_module(module_name)
    assert hasattr(module, short_name)

    test_class = getattr(module, short_name)(config, ssh_pool)
    assert isinstance(test_class, getattr(module, short_name))

    assert hasattr(test_class, 'setup')
    assert hasattr(test_class, 'teardown')
    assert hasattr(getattr(test_class, 'setup'), '__call__')
    assert hasattr(getattr(test_class, 'teardown'), '__call__')

    return test_class


@pytest.fixture
def local_config():
    config = {
        'environment': {
            'server_hosts': [
                '127.0.1.1'
            ],
            'servers_per_host': 1,
            'client_hosts': [
                '127.0.1.2'
            ],
            'username': '',
            'private_key_path': '',
            'home': '/var/tmp/tiden/local',
        },
    }
    config['ssh'] = {
        'username': config['environment']['username'],
        'private_key_path': config['environment']['private_key_path'],
        'home': str(config['environment']['home']),
    }
    hosts = set(config['environment']['server_hosts'] +
                config['environment'].get('client_hosts', []))
    config['ssh']['threads_num'] = floor(sqrt(len(hosts)))
    if config['ssh']['threads_num'] < cpu_count():
        config['ssh']['threads_num'] = cpu_count()
    config['ssh']['hosts'] = list(hosts)
    if config['environment'].get('env_vars'):
        config['ssh']['env_vars'] = config['environment']['env_vars']
    return config


@pytest.fixture
def with_dec_classpath(request):
    """
    This fixture temporary pulls in 'tiden/tests/res/decorators' folder to Python Path, thus allowing to import modules
    directly from resources. After test, Python Path is reverted to previous value.
    :param request:
    :return:
    """
    import sys
    import os.path
    old_sys_path = sys.path.copy()
    old_modules = set(sys.modules.copy())
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'res', 'decorators')))
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
    yield request
    sys.path = old_sys_path.copy()
    new_modules = set(sys.modules.copy())
    imported_modules = new_modules - old_modules
    for imported_module in imported_modules:
        del sys.modules[imported_module]


@pytest.fixture
def mock_pm(request):
    class MockPluginManager:
        def do(self, method, *args, **kwargs):
            pass
    yield MockPluginManager()

