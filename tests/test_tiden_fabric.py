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

import pytest
from tiden.tidenfabric import TidenFabric
from tiden.tidenconfig import TidenConfig

@pytest.fixture

def example_dict_config():
    c = {
        'clean': True,
        'environment': {
            'server_hosts': [
                '127.0.0.1',
            ],
            'servers_per_host': 1,
            'client_hosts': [
                '127.0.0.1',
            ],
            'clients_per_host': 1,
        },
        'ignite': {
            'pitr_enabled': True,
            'baseline_enabled': False,
        },
    }
    return c


def test_fabric_simple(example_dict_config):
    config = TidenFabric().setConfig(example_dict_config)

    assert 'config' == config.__doc__

    assert config.ignite
    assert "ignite" == config.ignite.__doc__
    assert config == config.ignite.__parent__

    # assert config.ignite == config.ignite.pitr_enabled.__parent__ # this is not true anymore
    assert config.ignite.pitr_enabled, "pitr_enabled should be True"
    assert "pitr_enabled" == config.ignite.pitr_enabled.__doc__

    assert 'config.ignite.pitr_enabled' == config.ignite.pitr_enabled.__name__()
    assert not config.ignite.baseline_enabled, "baseline_enabled should be False"
    assert not config.unknown_option_enabled, "unknown_option_enabled should be equal to False"


def test_fabric_not_assigned_option(example_dict_config):
    config = TidenFabric().setConfig(example_dict_config)

    assert 'config' == config.__doc__

    # unknown option with '_enabled' in name should be treated as AttrObj
    option = config.not_set_option_enabled
    assert hasattr(option, '__parent__')
    assert hasattr(option, '__name__')
    assert 'config.not_set_option_enabled' == config.not_set_option_enabled.__name__()
    assert hasattr(option, 'value')
    assert option.value is None

    # negating such AttrObj should return another AttrObj with inverted '__negated__' attribute
    assert not option is None
    assert not ~option is None
    assert (~option).value
    assert hasattr(option, '__negated__')
    assert not option.__negated__
    assert hasattr((~option), '__negated__')
    assert (~option).__negated__

    # other unknown options should be just None
    option1 = config.not_set_option
    assert not hasattr(option1, '__parent__')
    assert not hasattr(option1, '__name__')
    assert option1 is None

@pytest.fixture

def clean_fabric():
    TidenFabric().reset()


def test_fabric_update_dict_after_create(example_dict_config, clean_fabric):
    c = example_dict_config.copy()
    d = {'aa': 1}
    b = d
    d['bb'] = 2
    assert 2 == b['bb']
    class FFF:
        def __init__(self, o):
            self.q = o
    f = FFF(d)
    d['zz'] = 3
    assert 3 == f.q['zz']

    config = TidenFabric().getConfig(c)
    c['simple'] = 42
    c['artifacts'] = {
        'test_artifact': {
            'version': '1.0.0',
        }
    }
    assert 42 == config.simple
    assert '1.0.0' == config.artifacts.test_artifact.version

