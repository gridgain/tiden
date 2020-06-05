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
from ....util import print_green, print_red
from time import time


class IgniteControlThreadMixin(IgniteNodesMixin):
    """
    Provides callbacks for GeneralGridTestcase.run_console_thread
    """

    def __init__(self, *args, **kwargs):
        # print('IgniteControlThreadMixin.__init__')
        super().__init__(*args, **kwargs)

    def make_cluster_thread(self):
        alive_nodes = self.get_alive_additional_nodes() + self.get_alive_default_nodes()
        print_green('make jstack on alive nodes (%s) process' % alive_nodes)
        for node_idx in alive_nodes:
            if 'PID' in self.nodes[node_idx]:
                path_to_jstack = self.nodes[node_idx]['log'].replace('.log', '-`date +%d.%m.%Y-%H.%M.%S`.jstack')
                try:
                    self.ssh.exec_on_host(
                        self.nodes[node_idx]['host'], [
                            'jstack -l %s > %s &' % (self.nodes[node_idx]['PID'], path_to_jstack)
                        ]
                    )
                except Exception as e:
                    print_red('Error make jstack on node %s : %s' % (node_idx, str(e)))

    def make_cluster_jfr(self, duration, settings=None):
        alive_nodes = self.get_alive_additional_nodes() + self.get_alive_default_nodes()
        print_green('make jfr on alive nodes (%s) process, duration = %s' % (alive_nodes, duration))
        if not settings:
            if 'jfr_cfg' in self.config['artifacts'].keys():
                settings = self.config['remote']['suite_var_dir'] + '/jfr_cfg/gridgain.jfc'
            else:
                settings = 'profile'
        for node_idx in alive_nodes:
            if 'PID' in self.nodes[node_idx]:
                path_to_jfr = self.nodes[node_idx]['log'].replace('.log', '-$date_jfr.jfr')
                export = 'export date_jfr=`date +%d.%m.%Y-%H.%M.%S`'
                try:
                    self.ssh.exec_on_host(
                        self.nodes[node_idx]['host'], [
                            '%s;echo $date_jfr; jcmd %s JFR.start duration=%ss filename=%s settings=%s &'
                            % (export, self.nodes[node_idx]['PID'], duration, path_to_jfr, settings)
                        ]
                    )

                except Exception as e:
                    print_red('Error make jfr on node %s : %s' % (node_idx, str(e)))

    def make_cluster_heapdump(self, nodes=None, tag='test'):
        if nodes is None:
            nodes = self.get_all_alive_nodes()

        print_green('make heapdump on nodes (%s)' % (nodes))
        for node_idx in nodes:
            if 'PID' in self.nodes[node_idx]:
                path_to_heapdump = self.nodes[node_idx]['log'].replace(
                    '.log',
                    '-heapdump-{time}-{pid}-{tag}.hprof'.format(
                        pid=self.nodes[node_idx]['PID'],
                        time=time(),
                        tag=tag,
                    )
                )

                try:
                    self.ssh.exec_on_host(self.nodes[node_idx]['host'], [
                        'jmap -dump:format=b,file={path_to_heapdump} {pid}'.format(
                            path_to_heapdump=path_to_heapdump,
                            pid=self.nodes[node_idx]['PID'],
                        )
                    ])
                except Exception as e:
                    print_red('Error make heapdump on node %s : %s' % (node_idx, str(e)))

