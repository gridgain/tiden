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

import sys

from tiden.util import read_yaml_file, prettydict
from os.path import join, dirname
from tiden.apps.ignite.exchange_info import ExchangesCollection


def test_log_timestamp():
    t = ExchangesCollection._parse_ignite_log_time('11:31:37,998')
    assert str(t) == '11:31:37,998'
    assert t == 41497998


def _get_test_file_name(index, name):
    return join(dirname(__file__), 'res', 'exchanges', name + '.' + str(index) + '.yaml')

exch_test_data = {
    1: {
        'expected_nodes': [
            2,
            2,
            2,
            2,
            2,
        ],
        'exchanges': [
            (4, 1),
            (5, 0),
            (6, 0),
            (7, 0),
            (8, 0),
        ],
        'exchange_names': [
            '[4, 1] ChangeGlobalStateMessage',
            '[5, 0] NODE_JOINED',
            '[6, 0] NODE_FAILED',
            '[7, 0] NODE_JOINED',
            '[8, 0] NODE_FAILED',
        ],
        'exchange_finished': [
            True,
            True,
            True,
            True,
            False,
        ],
        'exchanges_merged': [
            [],
            [],
            [],
            [],
            [],
        ],
        'check_times': False,
    },

    2: {
        'expected_nodes': [
            2,
            2,
            2,
            2,
            2,
            2,
        ],
        'exchanges': [
            (4, 1),
            (5, 0),
            (6, 0),
            (7, 0),
            (8, 0),
            (9, 0),
        ],
        'exchange_names': [
            '[4, 1] ChangeGlobalStateMessage',
            '[5, 0] NODE_JOINED',
            '[6, 0] NODE_FAILED',
            '[7, 0] NODE_JOINED',
            '[8, 0] NODE_FAILED',
            '[9, 0] NODE_FAILED',
        ],
        'exchange_finished': [
            True,
            True,
            True,
            True,
            True,
            True,
        ],
        'exchanges_merged': [
            [],
            [],
            [],
            [],
            [(9, 0)],
            [(8, 0)],
        ],
        'check_times': True,
        'exchange_x1_time': [
            10993,
            5,
            4,
            3,
            31443,
            31443,
        ],
        'exchange_x2_time': [
            11015,
            12,
            12,
            8,
            31505,
            31505,
        ],
    },

    3: {
        'expected_nodes': [
            2,
            2,
            2,
            2,
            2,
            2,
            2,
            4,
            4,
            4,
        ],
        'exchanges': [
            (4, 1),
            (5, 0),
            (6, 0),
            (7, 0),
            (8, 0),
            (9, 0),
            (10, 0),
            (11, 0),
            (12, 0),
            (12, 1),
        ],
        'exchange_names': [
            '[4, 1] ChangeGlobalStateMessage',
            '[5, 0] NODE_JOINED',
            '[6, 0] NODE_FAILED',
            '[7, 0] NODE_JOINED',
            '[8, 0] NODE_JOINED',
            '[9, 0] NODE_FAILED',
            '[10, 0] NODE_FAILED',
            '[11, 0] NODE_JOINED',
            '[12, 0] NODE_JOINED',
            '[12, 1] CacheAffinityChangeMessage',
        ],
        'exchange_finished': [
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        ],
        'exchanges_merged': [
            [],
            [],
            [],
            [],
            [],
            [(10, 0)],
            [(9, 0)],
            [(12, 0)],
            [(11, 0)],
            [],
        ],
        'check_times': False,
    },
}


def _get_test_data(exch_test):
    print('Test data set #%s' % exch_test)

    start_exch = read_yaml_file(_get_test_file_name(exch_test, 'start_exch'))
    finish_exch = read_yaml_file(_get_test_file_name(exch_test, 'finish_exch'))
    merge_exch = read_yaml_file(_get_test_file_name(exch_test, 'merge_exch'))

    return ExchangesCollection.create_from_log_data(start_exch, finish_exch, merge_exch)


def test_exchange_info_names():
    for exch_test in exch_test_data.keys():
        exchanges = _get_test_data(exch_test)

        print(prettydict(exchanges))

        assert len(exch_test_data[exch_test]['exchanges']) == len(exchanges)

        for k, v in enumerate(exch_test_data[exch_test]['exchanges']):
            majv, minv = v
            exch_name = exch_test_data[exch_test]['exchange_names'][k]
            print('Exchange #{n}: ({majv}, {minv}), name="{name}"'.format(n=k, minv=minv, majv=majv, name=exch_name))
            exchange = exchanges.get_exchange(majv, minv)
            assert exchange is not None
            assert exch_name == str(exchange)


def test_exchange_info_get_non_existent_exchange():
    for exch_test in exch_test_data.keys():
        exchanges = _get_test_data(exch_test)
        assert exchanges.get_exchange(100, 1) is None
        break


def test_exchange_info_merged():
    for exch_test in exch_test_data.keys():
        exchanges = _get_test_data(exch_test)
        for k, v in enumerate(exch_test_data[exch_test]['exchanges']):
            major_topVer, minor_topVer = v
            merged_exchanges = set([ExchangesCollection.glue_version_num(*ex) for ex in exch_test_data[exch_test]['exchanges_merged'][k]])
            expect_merged = len(merged_exchanges) > 0
            exchange = exchanges.get_exchange(major_topVer, minor_topVer)
            if not expect_merged:
                assert expect_merged == exchange.merged
            else:
                assert expect_merged == exchange.merged, "Exchange %s expected merged to be %s" % (exchange, expect_merged)
                assert set(merged_exchanges) == exchange.merged_exchanges


def test_exchange_info_finished():
    for exch_test in exch_test_data.keys():
        exchanges = _get_test_data(exch_test)
        for k, v in enumerate(exch_test_data[exch_test]['exchanges']):
            expected_nodes = exch_test_data[exch_test]['expected_nodes'][k]
            major_topVer, minor_topVer = v
            expect_exchange_finished = exch_test_data[exch_test]['exchange_finished'][k]
            exchange = exchanges.get_exchange(major_topVer, minor_topVer)
            exchange_finished, n_nodes = exchanges.is_exchange_finished(major_topVer, minor_topVer, expected_nodes)
            assert expect_exchange_finished == exchange_finished, \
                "Exchange {name} was {expect} to be finished".format(
                    name=exchange,
                    expect='expected' if expect_exchange_finished else 'NOT expected'
                )


def test_exchange_info_x1_time():
    for exch_test in exch_test_data.keys():
        if exch_test_data[exch_test]['check_times']:
            exchanges = _get_test_data(exch_test)
            for k, v in enumerate(exch_test_data[exch_test]['exchanges']):
                major_topVer, minor_topVer = v
                expect_exchange_x1_time = exch_test_data[exch_test]['exchange_x1_time'][k]
                exchange_x1_time = exchanges.get_exchange_x1_time(major_topVer, minor_topVer)
                assert expect_exchange_x1_time == exchange_x1_time


def test_exchange_info_x2_time():
    for exch_test in exch_test_data.keys():
        if exch_test_data[exch_test]['check_times']:
            exchanges = _get_test_data(exch_test)
            for k, v in enumerate(exch_test_data[exch_test]['exchanges']):
                major_topVer, minor_topVer = v
                expect_exchange_x2_time = exch_test_data[exch_test]['exchange_x2_time'][k]
                exchange_x2_time = exchanges.get_exchange_x2_time(major_topVer, minor_topVer)
                assert expect_exchange_x2_time == exchange_x2_time


def test_exchange_info_grep_logs():
    from tiden.apps.ignite import Ignite
    from tiden.apps.nodestatus import NodeStatus
    from tiden.apps.ignite.components.ignitelogdatamixin import IgniteLogDataMixin

    class MockIgnite(Ignite):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        _collect_msg = IgniteLogDataMixin._collect_msg

        grep_all_data_from_log = IgniteLogDataMixin.grep_all_data_from_log

        def set_alive_nodes(self, *args):
            for i in args:
                self.nodes[i]['PID'] = i
                self.nodes[i]['status'] = NodeStatus.STARTED

        def set_test_data(self, start_node, end_node):
            self.nodes = {}
            for i in range(start_node, end_node + 1):
                self.nodes[i] = {
                    'log': _get_test_file_name(i, 'grid.' + self.grid_name + '.node.' + str(i) + '.1.log'),
                    'status': NodeStatus.KILLED,
                    'host': i,
                }

    from multiprocessing.dummy import Pool as ThreadPool
    import subprocess

    class MockSsh:
        def __init__(self):
            self.threads_num = 2

        def exec(self, commands, **kwargs):
            """
            :param commands: the list of commands to execute for hosts
            :return: the list of lines
            """
            from functools import partial
            commands_for_hosts = []
            # output = []
            # if isinstance(commands, list):
            #     for host in self.hosts:
            #         commands_for_hosts.append(
            #             [host, commands]
            #         )
            # elif isinstance(commands, dict):
            for host in commands.keys():
                commands_for_hosts.append(
                    [host, commands[host]]
                )
            # else:
            #     for host in self.hosts:
            #         commands_for_hosts.append(
            #             [host, [commands]]
            #         )
            pool = ThreadPool(self.threads_num)
            raw_results = pool.starmap(partial(self.exec_on_host, **kwargs), commands_for_hosts)
            results = {}
            for raw_result in raw_results:
                for host in raw_result.keys():
                    results[host] = raw_result[host]
            pool.close()
            pool.join()
            return results

        def exec_on_host(self, host, commands):
            output = []
            host_home = dirname(__file__)
            timeout = 60
            env = {}

            for command in commands:
                try:
                    # remove trailing redirect to stderr because we do it via stderr argument to check_output already
                    if command.endswith('2>&1'):
                        command = command[:-(len('2>&1'))]

                    proc_args = ['/usr/bin/env']
                    proc_args.extend(command.split(" "))

                    stdout = subprocess.check_output(
                        command,
                        shell=True,
                        # args=proc_args,
                        # executable=proc_args[0],
                        env=env,
                        cwd=host_home,
                        timeout=timeout,
                        stderr=subprocess.STDOUT
                    ).decode('utf-8')

                    output.append(stdout)  # .strip())
                except Exception as e:
                    pass

            return {host: output}

    config = {
        'environment': {

        }
    }
    ssh = MockSsh()

    ignite = MockIgnite('ignite', config, ssh, grid_name='run1')
    ignite.set_test_data(1, 10)
    ignite.set_alive_nodes(1, 3, 4, 9, 10)

    ex = ExchangesCollection.get_exchanges_from_logs(ignite, 'alive_server')
    print(prettydict(ex))

