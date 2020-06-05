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

from re import match, findall
from datetime import timedelta
from yaml import add_representer, add_constructor

from ...util import print_red, print_blue


class LogTimeStamp(int):
    yaml_tag = '!time'

    def __str__(self):
        v = self
        if v is None:
            return '?'
        s, m = divmod(v, 1000)
        return str(timedelta(seconds=s)) + ',' + str(m)

    @staticmethod
    def representer(dumper, data):
        return dumper.represent_scalar(LogTimeStamp.yaml_tag, str(data))

    @staticmethod
    def constructor(loader, node):
        value = loader.construct_scalar(node)
        return LogTimeStamp.parse_timestamp(value)

    @classmethod
    def parse_timestamp(cls, s):
        m = match('([0-9]+):([0-9]+):([0-9]+),([0-9]+)', s)
        if m:
            hours = int(m.group(1))
            mins = int(m.group(2))
            secs = int(m.group(3))
            msecs = int(m.group(4))
            return LogTimeStamp((((hours * 60) + mins) * 60 + secs) * 1000 + msecs)
        return LogTimeStamp(0)

add_representer(LogTimeStamp, LogTimeStamp.representer)
add_constructor(LogTimeStamp.yaml_tag, LogTimeStamp.constructor)


class ExchangeNodeInfo:
    started_init_time = None
    finished_exchange_time = None
    merged_time = None

    def __init__(self, **kwargs):
        self.update(**kwargs)

    def update(self, **kwargs):
        self.started_init_time = kwargs.get('started_init_time', self.started_init_time)
        self.finished_exchange_time = kwargs.get('finished_exchange_time', self.finished_exchange_time)
        if 'merged_time' in kwargs:
            if self.merged_time is None:
                self.merged_time = kwargs['merged_time']
            else:
                self.merged_time = max(self.merged_time, kwargs['merged_time'])


class ExchangeInfo:

    major_topVer = None
    minor_topVer = None
    exchange_event = None
    custom_event_name = None
    nodes_info = None
    merged_exchanges = None

    def __init__(self, **kwargs):
        self.nodes_info = {}
        self.merged_exchanges = set()
        self.update(**kwargs)

    def update(self, **kwargs):
        self.major_topVer = kwargs.get('major_topVer', self.major_topVer)
        self.minor_topVer = kwargs.get('minor_topVer', self.minor_topVer)
        self.exchange_event = kwargs.get('exchange_event', self.exchange_event)
        self.custom_event_name = kwargs.get('custom_event_name', self.custom_event_name)
        if 'node_idx' in kwargs:
            self.add_node_info(int(kwargs['node_idx']), **kwargs)

        if 'merged_exchange' in kwargs:
            self.merged_exchanges |= {kwargs['merged_exchange']}

    def add_node_info(self, node_index, **kwargs):
        if node_index not in self.nodes_info.keys():
            self.nodes_info[node_index] = ExchangeNodeInfo(**kwargs)
        else:
            self.nodes_info[node_index].update(**kwargs)

    def get_num_nodes(self):
        return len(self.nodes_info)

    def is_finished(self):
        n_started = 0
        n_finished = 0
        for node_info in self.nodes_info.values():
            if node_info.started_init_time is not None:
                n_started += 1
            if node_info.finished_exchange_time is not None:
                n_finished += 1
        return n_started == n_finished

    def is_merged(self):
        return len(self.merged_exchanges) > 0

    num_nodes = property(get_num_nodes, None)

    finished = property(is_finished, None)

    merged = property(is_merged, None)

    def __str__(self):
        def _str_event():
            if not self.exchange_event:
                return ''
            if not self.custom_event_name:
                return ' ' + self.exchange_event
            return ' ' + self.custom_event_name
        if self.minor_topVer is None:
            return '[' + str(self.major_topVer) + ', 0]' + _str_event()
        if self.major_topVer is None:
            assert False, "Exchange should have at least major topology version"
        return '[' + str(self.major_topVer) + ', ' + str(self.minor_topVer) + ']' + _str_event()


class ExchangesCollection(dict):

    run_id = 0

    @staticmethod
    def split_version_num(topVer):
        return divmod(topVer, 10000)

    @staticmethod
    def glue_version_num(major_topVer, minor_topVer):
        return int(major_topVer) * 10000 + int(minor_topVer)

    def add_exchange_info(self, topVer, **kwargs):
        major_topVer, minor_topVer = ExchangesCollection.split_version_num(topVer)
        if topVer not in self.keys():
            self[topVer] = ExchangeInfo(major_topVer=major_topVer, minor_topVer=minor_topVer, **kwargs)
        else:
            self[topVer].update(**kwargs)

    def get_exchange(self, major_topVer, minor_topVer):
        topVer = ExchangesCollection.glue_version_num(major_topVer, minor_topVer)
        return self.get(topVer, None)

    def get_min_merged_exchange(self, major_topVer):
        topVers = reversed(sorted(list(self.keys())))
        targVer = ExchangesCollection.glue_version_num(major_topVer, 0)
        found = False
        minVer = None
        merged_exchanges = set()
        for topVer in topVers:
            if not found:
                if topVer <= targVer:
                    found = True
                    minVer = topVer
                    merged_exchanges |= {topVer} | self[topVer].merged_exchanges
            else:
                if self[topVer].merged:
                    merges_intersect = self[topVer].merged_exchanges & merged_exchanges
                    if len(merges_intersect) > 0:
                        minVer = topVer
                        merged_exchanges = merged_exchanges | {topVer}
                else:
                    break
        return self[minVer]

    def get_max_merged_exchange(self, major_topVer):
        topVers = sorted(list(self.keys()))
        targVer = ExchangesCollection.glue_version_num(major_topVer, 0)
        found = False
        maxVer = None
        merged_exchanges = set()
        for topVer in topVers:
            if not found:
                if topVer >= targVer:
                    found = True
                    maxVer = topVer
                    merged_exchanges |= {topVer} | self[topVer].merged_exchanges
            else:
                if self[topVer].merged:
                    merges_intersect = self[topVer].merged_exchanges & merged_exchanges
                    if len(merges_intersect) > 0:
                        maxVer = topVer
                        merged_exchanges = merged_exchanges | {topVer}
                else:
                    break
        return self[maxVer]

    def is_exchange_finished(self, major_topVer, minor_topVer, n_expected_nodes):
        exchange = self.get_exchange(major_topVer, minor_topVer)
        if exchange is None:
            print('ERR: exchange %s, %s not found!' % (major_topVer, minor_topVer))
            return False, 0
        if exchange.merged:
            min_exch = self.get_min_merged_exchange(exchange.major_topVer)
            max_exch = self.get_max_merged_exchange(exchange.major_topVer)
            n_started = 0
            n_finished = 0
            for node_info in min_exch.nodes_info.values():
                if node_info.started_init_time is not None:
                    n_started += 1
            for node_info in max_exch.nodes_info.values():
                if node_info.finished_exchange_time is not None:
                    n_finished += 1

            print('INFO: exchange %s, %s: started: %s (%s), finished: %s (%s)' %
                  (major_topVer, minor_topVer, n_started, min_exch, n_finished, max_exch))

            return n_finished == n_expected_nodes, n_finished

        else:
            if exchange.num_nodes != n_expected_nodes:
                print('ERR: exchange %s, %s expected number of nodes do not match!' % (major_topVer, minor_topVer))
                return False, exchange.num_nodes

            n_started = 0
            n_finished = 0
            for node_info in exchange.nodes_info.values():
                if node_info.started_init_time is not None:
                    n_started += 1
                if node_info.finished_exchange_time is not None:
                    n_finished += 1

            print('INFO: exchange %s, %s: started: %s, finished: %s' %
                  (major_topVer, minor_topVer, n_started, n_finished))

            return n_started == n_finished, min(n_started, n_finished)

    def get_exchange_x2_time(self, major_topVer, minor_topVer=0):
        exchange = self.get(ExchangesCollection.glue_version_num(major_topVer, minor_topVer))
        if not exchange:
            return -1
        if exchange.merged:
            min_exch = self.get_min_merged_exchange(exchange.major_topVer)
            max_exch = self.get_max_merged_exchange(exchange.major_topVer)
        else:
            min_exch = exchange
            max_exch = exchange

        min_started = None
        max_finished = None
        for node_info in min_exch.nodes_info.values():
            if node_info.started_init_time is not None:
                if min_started is None:
                    min_started = node_info.started_init_time
                else:
                    min_started = min(node_info.started_init_time, min_started)
        for node_info in max_exch.nodes_info.values():
            if node_info.finished_exchange_time is not None:
                if max_finished is None:
                    max_finished = node_info.finished_exchange_time
                else:
                    max_finished = max(node_info.finished_exchange_time, max_finished)
        if max_finished is None:
            print_red("WARN: can't get maximum exchange finished time for %s" % exchange)
            return -1
        if min_started is None:
            print_red("WARN: can't get minimum exchange started time for %s" % exchange)
            return -1
        if min_started > max_finished:
            print_red("WARN: exchange %s was finished before started" % exchange)
        return max_finished - min_started

    def get_exchange_x1_time(self, major_topVer, minor_topVer=0):
        exchange = self.get(ExchangesCollection.glue_version_num(major_topVer, minor_topVer))
        if not exchange:
            return -1
        if exchange.merged:
            min_exch = self.get_min_merged_exchange(exchange.major_topVer)
            max_exch = self.get_max_merged_exchange(exchange.major_topVer)
        else:
            min_exch = exchange
            max_exch = exchange

        print_blue("INFO: min merged exchange: (%s), max merged exchange: (%s)" % (min_exch, max_exch))
        max_time = None
        node_ids = list(set(min_exch.nodes_info.keys()) and set(max_exch.nodes_info.keys()))
        for node_id in node_ids:
            node_info = min_exch.nodes_info.get(node_id)
            if node_info is None:
                print_red("WARN: exchange not found for node %s (%s)" % (min_exch, node_id))
                continue
            if node_info.started_init_time is None:
                print_red("WARN: 'Started exchange init' not found for node %s (%s)" % (node_id, min_exch))
                continue

            started_init_time = node_info.started_init_time

            node_info = max_exch.nodes_info.get(node_id)
            if node_info is None:
                print_red("WARN: exchange not found for node %s (%s)" % (max_exch, node_id))

            if node_info.finished_exchange_time is None:
                print_red("WARN: 'Finish exchange future' not found for node %s (%s)" % (node_id, min_exch))
                continue

            finished_exchange_time = node_info.finished_exchange_time

            node_time = finished_exchange_time - started_init_time
            if max_time is None:
                max_time = node_time
            else:
                if node_time > max_time:
                    max_time = node_time
        return max_time

    @staticmethod
    def _parse_top_ver(s):
        m = findall('[0-9]+', s)
        if m:
            return int(m[0]) * 10000 + int(m[1])
        return 0

    @staticmethod
    def _parse_ignite_log_time(s):
        return LogTimeStamp.parse_timestamp(s)

    @staticmethod
    def get_exchanges_from_logs(ignite, host_group='alive_server'):
        start_exch = ignite.grep_all_data_from_log(
            host_group,
            'Started exchange init',
            '\[([0-9,:]+)\]\[INFO\].*'
            '\[topVer=AffinityTopologyVersion \[(topVer=[0-9]+, minorTopVer=[0-9]+\]).*'
            'evt=([^,]*),.*(customEvt=([^ ]*)?)',
            'started_exchange_init',
            default_value='',
        )
        finish_exch = ignite.grep_all_data_from_log(
            host_group,
            'Finish exchange future',
            '\[([0-9,:]+)\]\[INFO\].*'
            'startVer=AffinityTopologyVersion \[(topVer=[0-9]+, minorTopVer=[0-9]+\]),'
            ' resVer=AffinityTopologyVersion \[(topVer=[0-9]+, minorTopVer=[0-9]+\])',
            'finish_exchange_future',
            default_value='',
        )

        merge_exch = ignite.grep_all_data_from_log(
            host_group,
            'Merge exchange future',
            '\[([0-9,:]+)\]\[INFO\].*'
            'curFut=AffinityTopologyVersion \[(topVer=[0-9]+, minorTopVer=[0-9]+\]),'
            ' mergedFut=AffinityTopologyVersion \[(topVer=[0-9]+, minorTopVer=[0-9]+\]).*'
            'evt=([^,]*),',
            'merge_exchange_future',
            default_value='',
        )

        # from tiden.util import write_yaml_file
        # from os.path import dirname, join
        # write_yaml_file(join(dirname(__file__), 'start_exch.%d.yaml' % ExchangesCollection.run_id), start_exch)
        # write_yaml_file(join(dirname(__file__), 'finish_exch.%d.yaml' % ExchangesCollection.run_id), finish_exch)
        # write_yaml_file(join(dirname(__file__), 'merge_exch.%d.yaml' % ExchangesCollection.run_id), merge_exch)
        # ExchangesCollection.run_id += 1
        return ExchangesCollection.create_from_log_data(start_exch, finish_exch, merge_exch)

    @staticmethod
    def create_from_log_data(start_exch_msgs, finish_exch_msgs, merge_exch_msgs):
        exch_by_topVer = ExchangesCollection()

        # collect 'Started exchange init'
        for node_idx, node_result in start_exch_msgs.items():
            for result in node_result:
                topVer = ExchangesCollection._parse_top_ver(result[1])
                start_time = ExchangesCollection._parse_ignite_log_time(result[0])
                event = result[2]
                custom_event = None if result[4] == 'null,' else result[4]
                exch_by_topVer.add_exchange_info(
                    topVer,
                    started_init_time=start_time,
                    exchange_event=event,
                    custom_event_name=custom_event,
                    node_idx=node_idx
                )

        # collect 'Finished exchange init' messages
        for node_idx, node_result in finish_exch_msgs.items():
            for result in node_result:
                res_topVer = ExchangesCollection._parse_top_ver(result[2])
                start_topVer = ExchangesCollection._parse_top_ver(result[1])
                end_time = ExchangesCollection._parse_ignite_log_time(result[0])
                exch_by_topVer.add_exchange_info(
                    res_topVer,
                    start_topVer=start_topVer,
                    finished_exchange_time=end_time,
                    node_idx=node_idx
                )

        # collect 'Merge exchange future' messages
        for node_idx, node_result in merge_exch_msgs.items():
            for result in node_result:
                cur_topVer = ExchangesCollection._parse_top_ver(result[1])
                merged_topVer = ExchangesCollection._parse_top_ver(result[2])
                event = result[3]
                merge_time = ExchangesCollection._parse_ignite_log_time(result[0])
                exch_by_topVer.add_exchange_info(
                    merged_topVer,
                    merged_exchange=cur_topVer,
                    merged_time=merge_time,
                    exchange_event=event,
                    node_idx=node_idx
                )
                exch_by_topVer.add_exchange_info(
                    cur_topVer,
                    merged_exchange=merged_topVer,
                    merged_time=merge_time,
                    node_idx=node_idx
                )

        return exch_by_topVer

