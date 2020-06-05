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
from time import sleep

TIDEN_PLUGIN_VERSION = '1.0.0'


class JavaKiller(TidenPlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def before_hosts_setup(self, *args, **kwargs):
        # Kill java process on hosts
        skip_ps_termination, another_user_ps = self.skip_process_termination()
        if skip_ps_termination:
            exit('WARNING: Found Java processes owned by another user')

        jps_func = self.ssh.jps
        if another_user_ps:
            jps_func = self.ssh.get_process_and_owners

        java_processes = jps_func()
        if len(java_processes) > 0:
            self.log_print('Existing java processes on hosts:')
            hosts_java_procs = set()
            for proc in java_processes:
                if proc['host'] not in hosts_java_procs:
                    cur_host = proc['host']
                    cur_procs = []
                    hosts_java_procs.add(cur_host)
                    for proc_for_host in java_processes:
                        if proc_for_host['host'] == cur_host:
                            cur_procs.append({'name': proc_for_host.get('name'), 'pid': proc_for_host.get('pid')})
                    if len(cur_procs) > 0:
                        self.log_print('\t%s:' % cur_host)
                        for cur_proc in cur_procs:
                            self.log_print('\t\t%s %s' % (cur_proc['pid'], cur_proc['name']))
            timeout_counter = 60
            if len(java_processes) > 0:
                self.log_put('Kill java processes on hosts: running %s' % len(java_processes))
                self.ssh.killall('java')
                while len(java_processes) > 0 and timeout_counter > 0:
                    java_processes = jps_func()
                    self.log_put('Kill java processes on hosts: running %s' % len(java_processes))
                    sleep(5)
                    timeout_counter -= 5
                self.log_print()
            if len(java_processes) > 1:
                self.log_print('ERROR: Unable to kill java processes', color='red')
                exit(1)
        else:
            self.log_print('No java processes found on hosts', color='green')

    def skip_process_termination(self):
        skip_termination, another_user_ps = False, False
        owner_processes = self.ssh.get_process_and_owners()
        for details in owner_processes:
            if details.get('owner') and details.get('owner') != self.config['environment']['username']:
                self.print_red(
                    'Find process with PID: %s by user: %s on host: %s' % (
                        details.get('pid'), details.get('owner'), details.get('host'))
                )
                another_user_ps = True
                if self.options.get('force_setup'):
                    self.print_red('Going to terminate processes from another user !!!')
                else:
                    skip_termination = True
        if skip_termination:
            self.print_red('force_setup flag is not set. Runner will be stopped !!!')
        return skip_termination, another_user_ps



