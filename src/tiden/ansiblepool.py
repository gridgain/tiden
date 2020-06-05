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

from collections import namedtuple

from ansible.parsing.dataloader import DataLoader
from ansible.plugins.callback.debug import CallbackModule
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase

from .sshpool import SshPool, log_print

SEPARATOR = '_THIS_IS_SEPARATOR_'


class AnsiblePool(SshPool):
    def __init__(self, ssh_config, **kwargs):
        super(AnsiblePool, self).__init__(ssh_config, **kwargs)

        Options = namedtuple('Options',
                             ['connection', 'module_path', 'forks', 'become', 'become_method', 'become_user', 'check',
                              'diff'])

        # initialize needed objects
        self.loader = DataLoader()
        self.options = Options(connection='smart', module_path='.', forks=100, become=None, become_method=None,
                               become_user=None, check=False, diff=False)
        self.passwords = dict(become_pass='')

        # create inventory and pass to var manager
        if len(self.hosts) == 1:
            # magic code (see ansible/inventory/manager.py:204)
            all_hosts = "%s," % str(self.hosts[0])
        else:
            all_hosts = ",".join(self.hosts)

        self.inventory = InventoryManager(loader=self.loader, sources=[all_hosts])
        self.variable_manager = VariableManager(loader=self.loader, inventory=self.inventory)

    def trace_info(self):
        log_print('Support environment through Ansible')

    def upload(self, files, remote_path):
        results_callback = DebugCallback()

        tasks = []
        for file in files:
            tasks.append(dict(action=dict(module='synchronize',
                                          src=file,
                                          dest=remote_path,
                                          # recursive='yes',
                                          # compress='yes',
                                          ),
                              register='shell_out'))

        self._run_ansible(results_callback, tasks)

    def upload_on_host(self, host, files, remote_dir):
        results_callback = CallbackModule()

        tasks = []
        for file in files:
            tasks.append(dict(action=dict(module='synchronize',
                                          src=file,
                                          dest=remote_dir,
                                          # recursive='yes',
                                          # compress='yes',
                                          ),
                              register='shell_out'))

        self._run_ansible(results_callback, tasks, host)

    def download(self, remote_path, local_path, prepend_host=True):
        results_callback = DebugCallback()

        if not local_path.endswith('/'):
            local_path = '%s/' % local_path

        if prepend_host:
            local_path = '%s/{{inventory_hostname}}/' % local_path

        tasks = [dict(action=dict(module='fetch',
                                  src=remote_path,
                                  dest=local_path,
                                  flat='yes'), register='shell_out')]

        self._run_ansible(results_callback, tasks)

    def download_from_host(self, host, remote_path, local_path):
        results_callback = DebugCallback()

        # fix local path
        if not local_path.endswith('/'):
            local_path.append('/')

        tasks = [dict(action=dict(module='fetch',
                                  src=remote_path,
                                  dest=local_path,
                                  flat='yes'), register='shell_out')]

        self._run_ansible(results_callback, tasks, host)

    def exec(self, commands, **kwargs):
        results_callback = TidenCallback()

        if isinstance(commands, list):
            tasks = []
            for command in commands:
                tasks.append(dict(action=dict(module='shell',
                                              args=self._escape_equals(command)), register='shell_out'))

            self._run_ansible(results_callback, tasks)
        elif isinstance(commands, dict):
            if len(commands.keys()) == 0:
                return

            hosts = ",".join(filter(lambda x: len(commands[x]) > 0,
                                    commands.keys()))

            # NB! This trick with separator may cause errors in test code if start string used in parsing regex
            # Because some strings may started with \n
            env_vars = ''
            if self.config.get('env_vars'):
                for env_var_name in self.config['env_vars'].keys():
                    env_vars += "%s=%s;" % (env_var_name, self.config['env_vars'][env_var_name])
            commands_per_host = {}
            for host in commands.keys():
                commands_per_host[host] = ''
                for command in commands[host]:
                    command = self._escape_equals(command)
                    if env_vars != '':
                        command = "%s%s" % (env_vars, command)
                    if len(command) > 0:
                        # to separate different commands output used special separator
                        # which will be used while parsing result for each command
                        separator = ' ;echo "%s"; ' % SEPARATOR
                        if '&' == command[-1]:
                            # & symbol is already "next command"
                            separator = ' echo "%s"; ' % SEPARATOR

                        commands_per_host[host] += command + separator

            variable_manager = VariableManager(loader=self.loader, inventory=self.inventory)

            variable_manager.extra_vars = {'commands_per_host': commands_per_host}

            tasks = [dict(action=dict(module='shell',
                                      args='{{vars.commands_per_host[inventory_hostname]}}'),
                          register='shell_out')]

            # print("\n------------------CMD_P----------------------")
            # print(commands_per_host)
            # print("\n------------------TASKS----------------------")
            # print(tasks)

            self._run_ansible(results_callback, tasks, hosts=hosts, variable_manager=variable_manager)

        return results_callback.result

    def exec_on_host(self, host, commands):
        results_callback = TidenCallback()

        tasks = []
        env_vars = ''
        if self.config.get('env_vars'):
            for env_var_name in self.config['env_vars'].keys():
                env_vars += "%s=%s;" % (env_var_name, self.config['env_vars'][env_var_name])
        for command in commands:
            if env_vars != '':
                command = "%s%s" % (env_vars, command)
            tasks.append(dict(action=dict(module='shell',
                                          args=command), register='shell_out'))

        self._run_ansible(results_callback, tasks, host)

        return results_callback.result

    def connect(self):
        results_callback = TidenPingCallback()

        tasks = [dict(action=dict(module='ping'), register='shell_out')]

        self._run_ansible(results_callback, tasks)

        for node_ip, status in results_callback.result.items():
            if not status:
                log_print('', 2)
                log_print('Error: node %s is not available\n' % node_ip)
                exit(1)
            else:
                log_print('Ping node %s: OK' % node_ip)

    def dirsize(self, dir_path, *args):
        return super().dirsize(dir_path, *args)

    def not_uploaded(self, files, remote_path):
        return super().not_uploaded(files, remote_path)

    def available_space(self):
        return super().available_space()

    def get_process_and_owners(self):
        return self.jps()

    def jps(self):
        return super().jps()

    def _run_ansible(self, results_callback, tasks, hosts='all', variable_manager=None):
        # create play with tasks
        variable_manager = self.variable_manager if variable_manager is None else variable_manager

        play_source = dict(
            name='Ansible Play',
            hosts=hosts,
            gather_facts='no',
            tasks=tasks
        )
        play = Play().load(play_source, variable_manager=self.variable_manager, loader=self.loader)
        # actually run it
        tqm = None
        try:
            tqm = TaskQueueManager(
                inventory=self.inventory,
                variable_manager=variable_manager,
                loader=self.loader,
                options=self.options,
                passwords=self.passwords,
                stdout_callback=results_callback,
            )
            tqm.run(play)
        finally:
            if tqm is not None:
                tqm.cleanup()

    @staticmethod
    def _escape_equals(command):
        if "=" in command:
            command = command.replace("=", "\=")
        return command


class DebugCallback(CallbackBase):
    def v2_runner_on_failed(self, result, ignore_errors=False):
        pass

    def v2_runner_on_ok(self, result, **kwargs):
        pass


class ResultCallback(CallbackBase):
    def __init__(self):
        super().__init__()

        self.result = {}


class TidenPingCallback(ResultCallback):
    def v2_runner_on_failed(self, result, ignore_errors=False):
        self.result[result._host.name] = str(result._result['ping']) == 'pong'

    def v2_runner_on_ok(self, result, **kwargs):
        self.result[result._host.name] = str(result._result['ping']) == 'pong'


class TidenCallback(ResultCallback):
    def v2_runner_on_failed(self, result, ignore_errors=False):
        # print(result._result['msg'])
        if result._host.name in self.result:
            self.result[result._host.name].append(str(result._result['msg']).split(SEPARATOR))
        else:
            self.result[result._host.name] = str(result._result['msg']).split(SEPARATOR)

    def v2_runner_on_ok(self, result, **kwargs):
        # print(result._result['stdout'])
        if result._host.name in self.result:
            self.result[result._host.name].append(str(result._result['stdout']).split(SEPARATOR))
        else:
            self.result[result._host.name] = str(result._result['stdout']).split(SEPARATOR)

