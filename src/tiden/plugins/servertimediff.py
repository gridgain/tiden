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

from tiden.tidenplugin import TidenPlugin
from re import search
from time import time

TIDEN_PLUGIN_VERSION = '1.0.0'


class ServerTimeDiff(TidenPlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command = 'date "+%s.%N"'
        self.acceptable_time_diff = self.options.get('acceptable_time_diff', 1000)

    def before_tests_run(self, *args, **kwargs):
        res = {}
        started = time()
        for host in self.ssh.hosts:
            res[host] = {'remote': None, 'local_started': time(), 'delay': 0}
            output = self.ssh.exec_on_host(host, [self.command])[host][0]
            m = search('^([0-9.]+)\n', str(output))
            if m:
                res[host]['remote'] = float(m.group(1))
            res[host]['local_finished'] = time()
            res[host]['diff'] = res[host]['remote'] - res[host]['local_started']
        self.log_print('Time check took %s sec' % (time() - started))

        max_diff = 0
        max_diff_host = None
        for host in self.ssh.hosts:
            cur_diff = res[host]['diff']
            if cur_diff > max_diff:
                max_diff = cur_diff
                max_diff_host = host
        check_result = max_diff < self.acceptable_time_diff
        message_color = 'green' if check_result else 'red'
        self.log_print('Max diff between localhost and %s: %.3f sec' % (max_diff_host, max_diff), color=message_color)
        return check_result

