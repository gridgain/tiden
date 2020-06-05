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


class IgniteBinRestMixin(IgniteLogDataMixin):
    """
    Provides access to Snapshot and Control utilities, instantiates on demand.

    Example:

        ignite = Ignite(...)
        ignite.cu.activate()
    """
    _cu = None

    def __init__(self, *args, **kwargs):
        # print('IgniteBinRestMixin.__init__')
        super(IgniteBinRestMixin, self).__init__(*args, **kwargs)

        self.add_node_data_log_parsing_mask(
            name='CommandPort',
            node_data_key='binary_rest_port',
            remote_regex='\[GridTcpRestProtocol\] Command protocol successfully started',
            local_regex='port=([0-9]+)\]',
            force_type='int'
        )
        self.add_node_data_log_parsing_mask(
            name='ClientConnectorPort',
            node_data_key='client_connector_port',
            remote_regex='\[ClientListenerProcessor\] Client connector processor has started on TCP port',
            local_regex='port ([0-9]+)',
            force_type='int'
        )

    def get_control_utility(self):
        if self._cu is None:
            from tiden.utilities.control_utility import ControlUtility
            self._cu = ControlUtility(self)
        return self._cu

    cu = property(get_control_utility, None)

