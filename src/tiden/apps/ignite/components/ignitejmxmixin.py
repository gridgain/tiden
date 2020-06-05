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

        self.add_node_data_log_parsing_mask(
            name='JMX',
            node_data_key='jmx_port',
            remote_regex='JMX (remote: on, port: [0-9]\+,',
            local_regex='JMX \(remote: on, port: (\d+),',
            force_type='int',
        )

    def get_jmx_utility(self):
        if self._jmx is None:
            from tiden.utilities import JmxUtility
            self._jmx = JmxUtility(self)
        return self._jmx

    jmx = property(get_jmx_utility, None)

