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

from tiden.tidenconfig import TidenConfig
import pytest

@pytest.fixture

def example_config():
    c = TidenConfig({
        'clean': True,
        'attrib': [
            'test_IGN_9715'
        ],
        'environment': {
            'server_hosts': [
                '127.0.0.1'
            ],
            'servers_per_host': 4,
        },
        'artifacts': {
            'ignite': {
                'type': 'ignite',
                'glob_path': './work/gridgain-enterprise-fabric-*.zip',
                'ignite_version': '2.4.2-p2',
                'gridgain_version': '8.4.2-p2',
            },
            'test_tools': {
                'glob_path': './work/ignite-test-tools-1.0.0*.jar',
            },
            'myclient': {
                'type': 'myclient',
                'glob_path': './work/my-client-java-0.1.jar',
            }
        },
        'remote': {
            'artifacts_dir': '/storage/ssd/johnsmith/tiden/artifacts'
        },
        'ssh': {
            'home': '/storage/ssd/johnsmith/tiden/',
            'hosts': [
                '127.0.0.1'
            ],
            'username': 'johnsmith',
            'threads_num': 8,
            'private_key_path': '/home/johnsmith/.ssh/johnsmith_keys',
        }
    })
    return c


def test_config_attr_simple(example_config):
    assert True == example_config.clean


def test_config_attr_list(example_config):
    assert ['test_IGN_9715'] == example_config.attrib


def test_config_attr_list_in_dict(example_config):
    assert '127.0.0.1' == example_config.environment.server_hosts[0]


def test_config_attr_remote(example_config):
    assert '/storage/ssd/johnsmith/tiden/artifacts' == example_config.remote.artifacts_dir


def test_config_attr_ssh(example_config):
    assert 'johnsmith' == example_config.ssh.username


def test_config_attr_num_artifacts(example_config):
    assert 3 == example_config.num_artifacts


def test_config_attr_num_attrib(example_config):
    assert 1 == example_config.num_attrib


def test_config_attr_num_server_hosts(example_config):
    assert 1 == example_config.environment.num_server_hosts


def test_config_attr_num_server_nodes(example_config):
    assert 4 == example_config.environment.num_server_nodes


def test_config_attr_num_client_hosts(example_config):
    assert 0 == example_config.environment.num_client_hosts


def test_config_attr_ignite_version(example_config):
    assert '2.4.2-p2' == example_config.ignite_version


def test_config_attr_gridgain_version(example_config):
    assert '8.4.2-p2' == example_config.gridgain_version

@pytest.fixture

def example_config_without_ignite():
    c = TidenConfig({
        'artifacts': {
            'test_tools': {
                'glob_path': './work/ignite-test-tools-1.0.0*.jar',
            },
            'myclient': {
                'type': 'myclient',
                'glob_path': './work/my-client-java-0.1.jar',
            }
        },
    })
    return c

@pytest.fixture

def example_config_with_renamed_ignite():
    c = TidenConfig({
        'artifacts': {
            'base': {
                'type': 'ignite',
                'ignite_version': '2.4.0',
            },
        },
    })
    return c


def test_config_attr_ignite_version_no_ignite_artifacts(example_config_without_ignite):
    assert example_config_without_ignite.ignite_version is None


def test_config_attr_ignite_version_with_renamed_ignite(example_config_with_renamed_ignite):
    assert '2.4.0' == example_config_with_renamed_ignite.ignite_version


def test_config_attr_ignite_by_name(example_config_with_renamed_ignite):
    assert '2.4.0' == example_config_with_renamed_ignite.artifacts['base'].ignite_version


def test_config_attr_unexistant_env_var(example_config_with_renamed_ignite):
    assert example_config_with_renamed_ignite.environment['servers_per_host'] is None

@pytest.fixture

def example_config_with_patches():
    c = TidenConfig({
        'simple': 45,
        'patched': '${simple}-!',
        'suite_name': 'self_test',
        'loop': 'a-${loop}-b',
        'environment': {
            'shared_home': '/mnt/lab_share01/${suite_name}'
        },
    })
    return c


def test_config_attr_unexistant_env(example_config_with_patches):
    assert 45 == example_config_with_patches.simple
    assert '45-!' == str(example_config_with_patches.patched)
    assert '/mnt/lab_share01/self_test' == str(example_config_with_patches.environment.shared_home)
    assert 'a-${loop}-b' == str(example_config_with_patches.loop)


def test_negative_requirement(example_config):
    assert True == (not example_config.feature_enabled)
    assert False == bool(example_config.feature_enabled)

