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

from .ignitenodesmixin import IgniteNodesMixin
from re import findall
from ....util import print_red


class IgniteLogDataMixin(IgniteNodesMixin):
    """
    Allows children class to hook into get_starting_node_attrs
    """
    log_masks = {}

    def __init__(self, *args, **kwargs):
        # print('IgniteLogDataMixin.__init__')
        super().__init__(*args, **kwargs)

    def add_node_data_log_parsing_mask(self, node_data_key, remote_regex, local_regex, name=None, force_type=None):
        self.log_masks[node_data_key] = {
            'remote_regex': remote_regex,
            'local_regex': local_regex,
            'name': node_data_key if name is None else name
        }
        if force_type is not None:
            self.log_masks[node_data_key]['type'] = force_type

    def get_log_masks(self):
        return self.log_masks

    def _collect_msg(self, msg_key, host_group='client'):
        res = {}
        nodes = self.get_all_default_nodes() if 'server' in host_group else self.get_all_common_nodes()
        for node_id in nodes:
            if msg_key in self.nodes[node_id] and self.nodes[node_id][msg_key]:
                res[node_id] = self.nodes[node_id][msg_key]
        return res

    def grep_all_data_from_log(self, host_group, grep_text, regex_match, node_option_name, **kwargs):
        """
        Get data for node logs.
        For host in (host_group) grep logs for (grep_text) and try to find (regex_match) in result.
        Result return to function call, also write to self.nodes (node_option_name)
        :param host_group:
                        options: 'server', 'client', 'alive_server', 'alive_client', 'alive', '*'
        :param grep_text:
        :param regex_match:
        :param node_option_name:
        :param kwargs:
                    default_value = if set, self.nodes (node_option_name) = default_value, if nothing find
        :return:
        """
        commands = {}
        result_order = {}

        if 'default_value' in kwargs:
            default_value = kwargs['default_value']

            for node_idx in self.nodes.keys():
                self.nodes[node_idx][node_option_name] = default_value

        if 'server' == host_group:
            node_idx_filter = (
                    self.get_all_additional_nodes() +
                    self.get_all_default_nodes()
            )
        elif 'client' == host_group:
            node_idx_filter = (
                    self.get_all_client_nodes() +
                    self.get_all_common_nodes()
            )
        elif 'alive_server' == host_group:
            node_idx_filter = (
                    self.get_alive_additional_nodes() +
                    self.get_alive_default_nodes()
            )
        elif 'alive_client' == host_group:
            node_idx_filter = (
                    self.get_alive_client_nodes() +
                    self.get_alive_common_nodes()
            )
        elif 'alive' == host_group:
            node_idx_filter = (
                self.get_all_alive_nodes()
            )
        elif '*' == host_group:
            node_idx_filter = (
                self.get_all_nodes()
            )
        else:
            assert False, "Unknown host group!"

        for node_idx in node_idx_filter:
            if 'log' in self.nodes[node_idx]:
                node_idx_host = self.nodes[node_idx]['host']
                if commands.get(node_idx_host) is None:
                    commands[node_idx_host] = []
                    result_order[node_idx_host] = []
                commands[node_idx_host].append('grep -E "%s" %s' % (grep_text, self.nodes[node_idx]['log']))
                result_order[node_idx_host].append(node_idx)
            else:
                print_red('There is no log for node %s' % node_idx)
        results = self.ssh.exec(commands)

        for host in results.keys():
            for res_node_idx in range(0, len(results[host])):
                m = findall(regex_match, results[host][res_node_idx])
                if m:
                    self.nodes[result_order[host][res_node_idx]][node_option_name] = m

        return self._collect_msg(node_option_name, host_group)

