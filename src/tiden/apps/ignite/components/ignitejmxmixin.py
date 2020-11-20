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

from .ignitelogdatamixin import IgniteLogDataMixin


class IgniteJmxMixin(IgniteLogDataMixin):
    grid_jmx_index = 0

    """
    Provides access to Jmx utility on demand.

    Example usage:

        ignite = Ignite(...)
        ignite.jmx.get_attributes()

    """

    _jmx = None

    def __init__(self, *args, **kwargs):
        # print('IgniteJmxMixin.__init__')
        super(IgniteJmxMixin, self).__init__(*args, **kwargs)

        self.grid_jmx_offset = IgniteJmxMixin.grid_jmx_index
        IgniteJmxMixin.grid_jmx_index = IgniteJmxMixin.grid_jmx_index + 1

        self.add_node_data_log_parsing_mask(
            name='JMX',
            node_data_key='jmx_port',
            remote_regex='JMX (remote: on, port: [0-9]\+,',
            local_regex='JMX \(remote: on, port: (\d+),',
            force_type='int',
        )

    def get_jmx_utility(self):
        raise NotImplementedError

    jmx = property(get_jmx_utility, None)

    def _get_node_JMX_options(self, node_idx):
        node_jmx_port = self._get_node_JMX_port(node_idx)
        if not node_jmx_port:
            return []
        return [
            '-Dcom.sun.management.jmxremote',
            '-Dcom.sun.management.jmxremote.port=' + str(node_jmx_port),
            '-Dcom.sun.management.jmxremote.ssl=false',
            '-Dcom.sun.management.jmxremote.authenticate=false',
        ]

    def _get_base_JMX_port(self):
        return 1100 + self.MAX_NODES_PER_HOST * 4 * (self.grid_jmx_offset - 1)

    def _get_node_JMX_port(self, node_idx):
        if self.is_default_node(node_idx):
            return \
                int(node_idx) + \
                self._get_base_JMX_port() - 1
        elif self.is_additional_node(node_idx):
            return \
                int(node_idx) + \
                self._get_base_JMX_port() - 1 - self.ADDITIONAL_NODE_START_ID + self.MAX_NODES_PER_HOST / 4
        elif self.is_client_node(node_idx):
            return \
                int(node_idx) + \
                self._get_base_JMX_port() - 1 - self.CLIENT_NODE_START_ID + 2 * (self.MAX_NODES_PER_HOST / 4)
        elif self.is_common_node(node_idx):
            return \
                int(node_idx) + \
                self._get_base_JMX_port() - 1 - self.COMMON_NODE_START_ID + 3 * (self.MAX_NODES_PER_HOST / 4)
        else:
            return 0
