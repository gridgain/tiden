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

from tiden.tidenpluginmanager import PluginManager
from os import environ
from copy import deepcopy


def check_env_expander(input_config, env_patch, _expected_config):
    for env_name, env_val in env_patch.items():
        environ[env_name] = env_val
    expected_config = deepcopy(_expected_config)
    del_plug = False
    if 'plugins' not in input_config:
        input_config['plugins'] = {}
        del_plug = True
    del_exp = False
    if 'EnvExpander' not in input_config['plugins']:
        del_exp = True
        input_config['plugins']['EnvExpander'] = {}
    pm = PluginManager(input_config)
    output_config = pm.do_filter('after_config_loaded', input_config)[0]
    if del_exp:
        del output_config['plugins']['EnvExpander']
    else:
        del output_config['plugins']['EnvExpander']['module']
    if del_plug:
        del output_config['plugins']
    assert expected_config == output_config


def test_env_expander_no_replace():
    input_config = {
        'environment': {
            'server_hosts': [],
        },
        'attr_match': 'any',
        'attrib': [
            'common'
        ],
    }
    check_env_expander(input_config, {}, input_config)


def test_env_expander_simple_replace():
    input_config = {
        'attr_match': '${ATTR_MATCH}',
    }
    env_patch = {
        'ATTR_MATCH': 'any'
    }
    expected_config = {
        'attr_match': 'any',
    }
    check_env_expander(input_config, env_patch, expected_config)


def test_env_expander_list_replace_no_expand():
    input_config = {
        'hosts': '${HOSTS}',
    }
    env_patch = {
        'HOSTS': '127.0.0.1,127.0.0.2'
    }
    expected_config = {
        'hosts': '127.0.0.1,127.0.0.2',
    }
    check_env_expander(input_config, env_patch, expected_config)


def test_env_expander_sub_replace():
    input_config = {
        'artifacts': {
            'ignite-${VERSION}': {
                'type': 'ignite',
                'glob_path': 'ftp://somewhere.net/releases/apache-ignite-${VERSION}.zip',
            },
        },
    }
    env_patch = {
        'VERSION': '2.5.0'
    }
    expected_config = {
        'artifacts': {
            'ignite-2.5.0': {
                'type': 'ignite',
                'glob_path': 'ftp://somewhere.net/releases/apache-ignite-2.5.0.zip',
            },
        }
    }
    check_env_expander(input_config, env_patch, expected_config)


def test_env_expander_list_replace_with_expansion():
    plugins_config = {
        'EnvExpander': {
            'expand_vars': 'VERSION',
        },
    }
    input_config = {
        'artifacts': {
            'ignite-${VERSION}': {
                'type': 'ignite',
                'glob_path': 'ftp://somewhere.net/releases/apache-ignite-${VERSION}.zip',
            },
        },
        'plugins': plugins_config,
    }
    env_patch = {
        'VERSION': '2.5.0,2.7.0'
    }
    expected_config = {
        'artifacts': {
            'ignite-2.5.0': {
                'type': 'ignite',
                'glob_path': 'ftp://somewhere.net/releases/apache-ignite-2.5.0.zip',
            },
            'ignite-2.7.0': {
                'type': 'ignite',
                'glob_path': 'ftp://somewhere.net/releases/apache-ignite-2.7.0.zip',
            },
        },
        'plugins': plugins_config,
    }
    check_env_expander(input_config, env_patch, expected_config)


def test_env_expander_list_replace_with_two_vars_expansion():
    plugins_config = {
        'EnvExpander': {
            'expand_vars': [
                'VERSION',
                'SOURCE',
            ],
        },
    }
    input_config = {
        'artifacts': {
            '${SOURCE}-${VERSION}': {
                'type': 'ignite',
                'glob_path': 'ftp://somewhere.net/releases/${SOURCE}-${VERSION}.zip',
            },
        },
        'plugins': plugins_config,
    }
    env_patch = {
        'VERSION': '2.5.0,2.7.0',
        'SOURCE': 'apache-ignite,gridgain-community',
    }
    expected_config = {
        'artifacts': {
            'apache-ignite-2.5.0': {
                'type': 'ignite',
                'glob_path': 'ftp://somewhere.net/releases/apache-ignite-2.5.0.zip',
            },
            'apache-ignite-2.7.0': {
                'type': 'ignite',
                'glob_path': 'ftp://somewhere.net/releases/apache-ignite-2.7.0.zip',
            },
            'gridgain-community-2.5.0': {
                'type': 'ignite',
                'glob_path': 'ftp://somewhere.net/releases/gridgain-community-2.5.0.zip',
            },
            'gridgain-community-2.7.0': {
                'type': 'ignite',
                'glob_path': 'ftp://somewhere.net/releases/gridgain-community-2.7.0.zip',
            },
        },
        'plugins': plugins_config,
    }
    check_env_expander(input_config, env_patch, expected_config)


def test_env_expander_simple_lambda():
    plugins_config = {
        'EnvExpander': {
            'compute_vars': {
                'GRIDGAIN_VERSION': 'e["IGNITE_VERSION"].replace("2.", "8.")'
            }
        }
    }
    input_config = {
        'version': '${GRIDGAIN_VERSION}',
        'plugins': plugins_config,
    }
    env_patch = {
        'IGNITE_VERSION': '2.5.0',
    }
    expected_config = {
        'version': '8.5.0',
        'plugins': plugins_config,
    }
    check_env_expander(input_config, env_patch, expected_config)


def test_env_expander_list_lambda():
    plugins_config = {
        'EnvExpander': {
            'compute_vars': {
                'PREV_GRIDGAIN_VERSION': 'e["PREV_IGNITE_VERSION"].replace("2.", "8.")',
                'GRIDGAIN_VERSION': 'e["IGNITE_VERSION"].replace("2.", "8.")',
            },
            'expand_vars': [
                'PREV_IGNITE_VERSION',
            ]
        }
    }
    input_config = {
        'artifacts': {
            'base-${PREV_GRIDGAIN_VERSION}': {
                'type': 'ignite',
                'glob_path': './work/gridgain-community-${PREV_GRIDGAIN_VERSION}.zip',
            },
            'test': {
                'type': 'ignite',
                'glob_path': './work/gridgain-community-${GRIDGAIN_VERSION}.zip'
            }
        },
        'plugins': plugins_config,
    }
    env_patch = {
        'IGNITE_VERSION': '2.6.0',
        'PREV_IGNITE_VERSION': '2.5.0,2.5.1',
    }
    expected_config = {
        'artifacts': {
            'base-8.5.0': {
                'type': 'ignite',
                'glob_path': './work/gridgain-community-8.5.0.zip',
            },
            'base-8.5.1': {
                'type': 'ignite',
                'glob_path': './work/gridgain-community-8.5.1.zip',
            },
            'test': {
                'type': 'ignite',
                'glob_path': './work/gridgain-community-8.6.0.zip',
            },
        },
        'plugins': plugins_config,
    }
    check_env_expander(input_config, env_patch, expected_config)

