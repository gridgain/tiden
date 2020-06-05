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


class IgniteCommunicationMixin(IgniteLogDataMixin):
    """
    Provides useful wrappers over Ignite HTTP Communication protocol
    """

    def __init__(self, *args, **kwargs):
        super(IgniteCommunicationMixin, self).__init__(*args, **kwargs)

        self.add_node_data_log_parsing_mask(
            name='Communication',
            node_data_key='communication_port',
            remote_regex='Successfully bound communication NIO server to TCP port',
            local_regex='port=([0-9]+)',
            force_type='int',
        )

