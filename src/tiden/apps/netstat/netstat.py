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

from time import sleep, time

from ...util import *
from ..app import App


class Netstat(App):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hosts = list(set(self.ssh.hosts))
        self.pids = {}

    def network(self):
        result = {}
        res = self.ssh.exec(['/sbin/ifconfig'])
        for host in res.keys():
            result[host] = {}
            intf_name = None
            buffer = []
            for line in res[host][0].split('\n'):
                buffer.append(line)
                m = search('^([a-z0-9]+)\: (.+)$', line)
                if m:
                    intf_name = m.group(1)
                    if not result[host].get(intf_name):
                        result[host][intf_name] = {}
                m = search('(TX|RX)\s+(packets)\s+([0-9]+)\s+(bytes)\s+([0-9]+)', line)
                if m:
                    traffic_direction = m.group(1)
                    if not intf_name:
                        pass
                        # log_print('WARN: Found TX|TR for unknown interface in buffer\n {}'.format('\n'.join(buffer)),
                        #           level='debug')
                    else:
                        if not result[host][intf_name].get(traffic_direction):
                            result[host][intf_name][traffic_direction] = {}
                        else:
                            pass
                            # TODO fix debug level
                            # print_debug(
                            #     'WARN: Found TX|TR for unknown interface in buffer\n {}'.format('\n'.join(buffer)))
                        result[host][intf_name][traffic_direction][m.group(2)] = m.group(3)
                        result[host][intf_name][traffic_direction][m.group(4)] = m.group(5)
                    # cleanup buffer for current interface as soon as we've fount TX and RX (len == 2) components
                    if intf_name and len(result[host][intf_name]) == 2:
                        buffer = []
                        intf_name = None
        for host in result.keys():
            total = {}
            for intf_name in result[host].keys():
                for traffic_direction in result[host][intf_name].keys():
                    for measure_unit in result[host][intf_name][traffic_direction].keys():
                        if not total.get(traffic_direction):
                            total[traffic_direction] = {}
                        if not total[traffic_direction].get(measure_unit):
                            total[traffic_direction][measure_unit] = 0
                        total[traffic_direction][measure_unit] \
                            += int(result[host][intf_name][traffic_direction][measure_unit])
            result[host]['total'] = total
        return result

