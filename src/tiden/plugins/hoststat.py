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

from tiden.tidenplugin import TidenPlugin, TidenPluginScope
from time import sleep
from re import search

TIDEN_PLUGIN_VERSION = '1.0.0'


class HostStat(TidenPlugin):

    start_commands_template = {
        'dstat': 'nohup dstat --epoch --cpu --disk --io --net --sys --tcp --unix --mem '
                 '--output={report_dir}/hoststat_dstat.csv > /dev/null 2>&1 &',
        'iostat': 'nohup iostat -xtmd 1 >> {report_dir}/hoststat_iostat.log 2>&1 &',
        'mpstat': 'nohup mpstat -P ALL 1 >> {report_dir}/hoststat_mpstat.log 2>&1 &',
        'vmstat': 'nohup vmstat -S k  -a -t -w 1 >> {report_dir}/hoststat_vmstat.log 2>&1 &',
        'top': 'nohup top -b >> {report_dir}/hoststat_top.log 2>&1 &',
    }
    # stop_commands_template = {
    #     'dstat': 'sudo killall -9 dstat',
    #     'iostat': 'sudo killall -9 iostat',
    #     'mpstat': 'sudo killall -9 mpstat',
    #     'top': 'sudo killall -9 top',
    # }

    # default behaviour is to collect statistics during whole test run
    scope = TidenPluginScope.RUN

    # whether to do 'killall' before test session to cleanup from any previous runs
    cleanup = True

    pids = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.scope = TidenPluginScope.from_options(self.name, self.options, self.scope)

        self.cleanup = self.options.get('cleanup', self.cleanup)

        # Remove unused apps
        for stat_app in self.start_commands_template.copy().keys():
            if stat_app not in self.options.get('apps', {}):
                del self.start_commands_template[stat_app]
                # del self.stop_commands_template[stat_app]

        # Replace default command line for an app if its configuration provides specific one
        for stat_app in self.options.get('apps', {}).keys():
            if self.options['apps'][stat_app].get('start'):
                self.start_commands_template[stat_app]['start'] = self.options['apps'][stat_app]['start']
            # if self.options['apps'][stat_app].get('stop'):
            #     self.stop_commands_template[stat_app]['stop'] = self.options['apps'][stat_app]['stop']

        self.__reset()

    def before_tests_run(self, *args, **kwargs):
        if self.cleanup:
            self.__cleanup()

        if self.scope == TidenPluginScope.RUN:
            self.__start(*args, **kwargs)

        return True

    def after_tests_run(self, *args, **kwargs):
        if self.scope == TidenPluginScope.RUN:
            self.__stop(*args, **kwargs)

    def before_test_class_setup(self, *args, **kwargs):
        if self.scope == TidenPluginScope.CLASS:
            self.__start(*args, **kwargs)

    def after_test_class_teardown(self, *args, **kwargs):
        if self.scope == TidenPluginScope.CLASS:
            self.__stop(*args, **kwargs)

    def before_test_method_setup(self, *args, **kwargs):
        if self.scope == TidenPluginScope.METHOD:
            self.__start(*args, **kwargs)

    def after_test_method_teardown(self, *args, **kwargs):
        if self.scope == TidenPluginScope.METHOD:
            self.__stop(*args, **kwargs)

    def __reset(self):
        self.start_commands = {}
        self.stop_commands = {}
        self.pids = {}

    def __apply_vars(self):
        self.__reset()
        # Apply report_dir
        remote_dir = self.scope.scoped_remote_dir(self.config)
        for stat_app in self.start_commands_template.keys():
            self.start_commands[stat_app] = self.start_commands_template[stat_app].format(
                report_dir=remote_dir
            )
        # for stat_app in self.stop_commands_template.keys():
        #     self.stop_commands[stat_app] = self.stop_commands_template[stat_app].format(
        #         report_dir=remote_dir
        #     )

    def __start(self, *args, **kwargs):
        # self.__stop(*args, **kwargs)
        self.__apply_vars()
        self.log_print("Start %s" % ', '.join(self.start_commands.keys()))
        # start
        self.ssh.exec(list(self.start_commands.values()))

        sleep(2)

        # get pids
        for command in self.start_commands.keys():
            if not command in self.pids.keys():
                self.pids[command] = {}
            result = self.ssh.exec(['ps -C %s --no-headers' % command])
            for host in result.keys():
                m = search('^\s*([0-9]+)', result[host][0])
                if m:
                    self.pids[command][host] = m.group(1)

    def __stop(self, *args, **kwargs):
        self.log_print("Stop %s" % ', '.join(self.start_commands.keys()))
        # self.ssh.exec(list(self.stop_commands.values()))
        for command in self.pids.keys():
            kill_pid_commands = {}
            for host in self.pids[command].keys():
                kill_pid_commands[host] = ['kill -9 %s' % self.pids[command][host]]
            self.ssh.exec(kill_pid_commands)

    def __cleanup(self, *args, **kwargs):
        self.log_print("Cleanup previous stats progs: %s" % ', '.join(self.start_commands_template.keys()))
        for command in list(self.start_commands_template.keys()):
            self.ssh.killall(command)
