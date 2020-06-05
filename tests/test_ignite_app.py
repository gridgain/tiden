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

from tiden.apps.ignite.ignite import Ignite


def test_ignite_jvm_options():
    server_host = '127.0.0.1'
    config = {
        'enable_jfr_and_gc_logs': True,
        'environment': {
            'server_hosts': [
                server_host,
            ],
            'client_hosts': [
                '127.0.0.2',
            ],
            'server_jvm_options': [
                '-XX:+UseG1GC',
                '-Xloggc:${tiden.filename}-gc-${tiden.node_id}.${tiden.run_counter}.log'
            ],
            'client_jvm_options': [
                '-XX:+UseParNewGC',
            ],
        },
        'rt': {
            'remote': {
                'test_module_dir': '/REMOTE_TEST_MODULE_DIR',
                'test_dir': '/REMOTE_TEST_DIR',
            }
        },
        'remote': {
            'suite_var_dir': '/REMOTE_SUITE_VAR_DIR',
        },
        'artifacts': {
            'ignite': {
                'path': None,
                'remote_path': '/REMOTE_ARTIFACT_DIR',
            }
        },
    }

    class MockSsh:
        def __init__(self, *args, **kwargs):
            pass
        def exec_on_host(self, *args, **kwargs):
            return {args[0]: ['']}
        def exec(self, *args, **kwargs):
            pass
    ssh = MockSsh(config)
    ignite_app = Ignite('ignite', config, ssh)
    ignite_app.setup()
    ignite_app.set_node_option('*', 'config', 'mock.xml')

    # default JVM options should come from environment
    start_commands = ignite_app._get_start_node_commands(Ignite.START_NODE_IDS + 1)
    assert 'UseG1GC' in start_commands[server_host][0]

    # adding options on the fly should not remove environment options
    ignite_app.set_node_option('*', 'jvm_options', ['-XX:+UnlockCommercialOptions'])

    start_commands = ignite_app._get_start_node_commands(Ignite.START_NODE_IDS + 1)
    assert 'UseG1GC' in start_commands[server_host][0]
    assert 'UnlockCommercialOptions' in start_commands[server_host][0]

    ignite_app.nodes[Ignite.START_NODE_IDS + 1]['run_counter'] = 41
    ignite_app.set_grid_name('mygrid')
    start_commands = ignite_app._get_start_node_commands(Ignite.START_NODE_IDS + 1)
    print(start_commands[server_host][0])
    assert '.mygrid.node.1.42.' in start_commands[server_host][0]
    assert '-gc-1.42.'in start_commands[server_host][0]

