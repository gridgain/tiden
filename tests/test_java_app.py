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

from .conftest import check_runtests_protocol
from os.path import join, dirname


def test_wrap_exec():
    hosts = [
        '127.0.1.1',
        '127.0.1.2',
    ]
    nodes = {
        0: {
            'host': '127.0.1.1',
            'log': 'blah.0.log',
        },
        1: {
            'host': '127.0.1.1',
            'log': 'blah.1.log',
        },
        2: {
            'host': '127.0.1.2',
            'log': 'blah.2.log',
        },
        3: {
            'host': '127.0.1.2',
            'log': 'blah.3.log',
        },
    }

    cmd_lambda = lambda node_idx, node: f'echo "Hello {node_idx}" > {node["log"]}'
    nodes_hosts = list(set([node['host'] for node in nodes.values()]))
    host_nodes = {host: [node_idx for node_idx, node in nodes.items() if node['host'] == host] for host in nodes_hosts}
    commands = {host: [cmd_lambda(node_idx, nodes[node_idx]) for node_idx in host_nodes[host]] for host in nodes_hosts}
    assert 2 == len(commands)
    assert '127.0.1.1' in commands
    assert '127.0.1.2' in commands
    assert 2 == len(commands['127.0.1.1'])
    assert 2 == len(commands['127.0.1.2'])
    assert f'echo "Hello 0" > blah.0.log' == commands['127.0.1.1'][0]
    assert f'echo "Hello 1" > blah.1.log' == commands['127.0.1.1'][1]
    assert f'echo "Hello 2" > blah.2.log' == commands['127.0.1.2'][0]
    assert f'echo "Hello 3" > blah.3.log' == commands['127.0.1.2'][1]

    output = {
        '127.0.1.1': [
            "Hello 0",
            "Hello 1",
        ],
        '127.0.1.2': [
            "Hello 2",
            "Hello 3",
        ]
    }
    node_output = {node_idx: host_nodes[node['host']].index(node_idx) for node_idx, node in nodes.items()}
    result = {node_idx: output[node['host']][node_output[node_idx]] for node_idx, node in nodes.items()}
    assert 4 == len(result)
    assert "Hello 0" == result[0]
    assert "Hello 1" == result[1]
    assert "Hello 2" == result[2]
    assert "Hello 3" == result[3]


def test_java_app(with_java_app_classpath, local_config, tmpdir, mock_pm):
    from tiden.result import Result
    from tiden.localpool import LocalPool
    from tiden.tidenfabric import TidenFabric
    from copy import deepcopy
    from datetime import datetime

    var_dir = str(tmpdir.mkdir('var'))
    xunit_file = str(tmpdir.join('var').join('xunit.xml'))
    tmpdir.join('var').join('xunit.xml').write('', ensure=True)
    report_path = 'report.yaml'

    config = deepcopy(local_config)

    config.update({
        'suite_name': 'mock',
        'test_name': '*',
        'suite_dir': join(dirname(__file__), 'res', 'java_app', 'suites'),
        'dir_prefix': f'mock-{datetime.now().strftime("%y%m%d-%H%M%S")}',
    })
    config.update({
        'suite_var_dir': str(tmpdir.join('var').mkdir(config['dir_prefix'])),
        'remote': {
            'artifacts': join(config['environment']['home'], 'artifacts'),
            'suite_var_dir': join(config['environment']['home'], config['dir_prefix']),
        },
        'config_path': str(tmpdir.join('var').join('config.yaml')),
    })
    config.update({
        'artifacts': {
            'mockapp': {
                'type': 'mockapp',
                'path': join(var_dir, 'artifacts', 'mockapp'),
                'remote_path': join(config['remote']['artifacts'], 'mockapp'),
            }
        },
    })

    ssh_pool = LocalPool(local_config['ssh'])
    res = Result(xunit_path=xunit_file)
    modules = {
        'mock.mock_test_app': {
            'path': '%s/mock/mock_test_app.py' % config['suite_dir'],
            'module_short_name': 'mock_test_app',
        },
    }
    from tiden.tidenrunner import TidenRunner
    ssh_pool.connect()
    TidenFabric().setSshPool(ssh_pool)
    TidenFabric().setConfig(config)
    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    tr.process_tests()
    res = tr.get_tests_results()
    res.flush_xunit()
    res.create_testrail_report(config, report_file=str(report_path))

