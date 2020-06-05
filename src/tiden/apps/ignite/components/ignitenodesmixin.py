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

from ...nodestatus import NodeStatus
from .ignitemixin import IgniteMixin
from random import choice


class IgniteNodesMixin(IgniteMixin):
    """
    Provides nodes filtering and manipulation methods
    """

    START_NODE_IDS = 0
    ADDITIONAL_NODE_START_ID = 10000
    CLIENT_NODE_START_ID = 50000
    COMMON_NODE_START_ID = 20000
    MAX_NODE_START_ID = 100000

    start_server_idx = 1
    start_client_idx = 1

    def __init__(self, *args, **kwargs):
        # print('IgniteNodesMixin.__init__')
        super().__init__(*args, **kwargs)
        self.start_client_idx = kwargs.get('start_client_idx', 1)
        self.start_server_idx = kwargs.get('start_server_idx', 1)

    def get_start_server_idx(self):
        return self.START_NODE_IDS + self.start_server_idx

    def get_start_client_idx(self):
        return self.COMMON_NODE_START_ID + self.start_client_idx

    def is_default_node(self, node_idx):
        return self.START_NODE_IDS < node_idx < self.ADDITIONAL_NODE_START_ID

    def is_additional_node(self, node_idx):
        return self.ADDITIONAL_NODE_START_ID < node_idx < self.COMMON_NODE_START_ID

    def is_common_node(self, node_idx):
        return self.COMMON_NODE_START_ID < node_idx < self.CLIENT_NODE_START_ID

    def is_client_node(self, node_idx):
        return self.CLIENT_NODE_START_ID < node_idx < self.MAX_NODE_START_ID

    def get_random_server_nodes(self, num_servers, use_coordinator=False, node_ids=None):
        """
        get up to num_servers random server node ids.
        if use_coordinator is True then coordinator will be surely included.
        if use_coordinator is False then coordinator will be NOT included.
        :param num_servers:
        :param use_coordinator:
        :return:
        """
        result = []
        if node_ids is None:
            all_servers = self.get_all_default_nodes() + self.get_all_additional_nodes()
        else:
            all_servers = node_ids.copy()
        coordinator_id = min(all_servers)
        if use_coordinator:
            result.append(coordinator_id)
        while len(result) < num_servers:
            if len(all_servers) > 0:
                srv = choice(all_servers)
                if not use_coordinator and srv != coordinator_id:
                    result.append(srv)
                all_servers.remove(srv)
            else:
                break
        return result

    def get_all_alive_nodes(self):
        return list(filter(lambda x: (self.START_NODE_IDS < x < self.MAX_NODE_START_ID) and (
                (self.is_common_node(x) and 'gateway' in self.nodes[x]) or
                (not self.is_common_node(x) and self.nodes[x]['status'] == NodeStatus.STARTED)), self.nodes.keys()))

    def get_all_nodes(self):
        return list(filter(lambda x: self.START_NODE_IDS < x < self.MAX_NODE_START_ID, self.nodes.keys()))

    def get_all_default_nodes(self):
        return list(filter(lambda x: self.is_default_node(x), self.nodes.keys()))

    def get_all_common_nodes(self):
        return list(filter(lambda x: self.is_common_node(x), self.nodes.keys()))

    def get_all_additional_nodes(self):
        return list(filter(lambda x: self.is_additional_node(x), self.nodes.keys()))

    def get_all_client_nodes(self):
        return list(filter(lambda x: self.is_client_node(x), self.nodes.keys()))

    def get_alive_default_nodes(self):
        return list(filter(lambda x: self.is_default_node(x) and self.nodes[x]['status'] == NodeStatus.STARTED,
                           self.nodes.keys()))

    def get_alive_common_nodes(self):
        return list(filter(lambda x: self.is_common_node(x) and 'gateway' in self.nodes[x], self.nodes.keys()))

    def get_alive_client_nodes(self):
        return list(filter(lambda x: self.is_client_node(x) and self.nodes[x]['status'] == NodeStatus.STARTED,
                           self.nodes.keys()))

    def get_alive_additional_nodes(self):
        return list(filter(lambda x: self.is_additional_node(x) and self.nodes[x]['status'] == NodeStatus.STARTED,
                           self.nodes.keys()))

    def get_last_node_id(self, node_type):
        if node_type == 'client':
            return max([node_index for node_index in self.nodes.keys() if self.is_client_node(node_index)])
        else:
            return max([node_index for node_index in self.nodes.keys() if self.is_default_node(node_index)])

