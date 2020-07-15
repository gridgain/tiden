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

from tiden import log_print, TidenException
from tiden.apps import App, NodeStatus


class JavaApp(App):
    default_jvm_options = [
        '-Djava.net.preferIPv4Stack=true',
        '-Djava.net.preferIPv6Addresses=false',
    ]
    class_name = ''
    start_timeout = 5

    java_app_jar = None
    java_app_home = None

    app_mode = 'client'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_mode = kwargs['app_mode'] if 'app_mode' in kwargs and kwargs['app_mode'] else self.__class__.app_mode
        self.num_nodes = kwargs.get('num_nodes', None)
        self.start_timeout = self.__class__.start_timeout
        self.jvm_options = self.__class__.default_jvm_options.copy()
        env_jvm_options = self.get_env_jvm_options(self.app_mode)
        if env_jvm_options:
            self.jvm_options.extend(env_jvm_options)
        self.class_name = self.__class__.class_name

    def setup(self):
        super().setup()
        self.java_app_jar = self.config['artifacts'][self.app_type]['remote_path']
        self.java_app_home = f"{self.remote_test_module_dir}/{self.name}"
        self.add_nodes(mode=self.app_mode)

    def add_nodes(self, mode='client'):
        for host in self.get_hosts(mode=mode):
            for host_node in range(0, self.get_nodes_per_host(mode=mode)):
                if self.num_nodes:
                    if len(self.nodes) >= self.num_nodes:
                        continue
                self.add_node(host, mode=mode)

    def add_node(self, host=None, mode='client'):
        node_idx = len(self.nodes)
        self.nodes[node_idx] = {
            'host': host,
            'status': NodeStatus.NEW,
            'run_dir': self.get_node_run_dir(mode, node_idx)
        }

    def rotate_node_log(self, node_idx):
        run_counter = 0 if 'run_counter' not in self.nodes[node_idx] else self.nodes[node_idx]['run_counter'] + 1
        self.nodes[node_idx].update({
            'run_counter': run_counter,
            'log': f"{self.remote_test_dir}/{self.name}.node.{node_idx}.{run_counter}.log",
        })

    def start_nodes(self):
        start_command = {}
        pids = {}
        nodes_to_start = []
        for node_idx, node in self.nodes.items():
            self.rotate_node_log(node_idx)
            nodes_to_start.append(node_idx)
            host = node['host']
            if host not in start_command:
                start_command[host] = []
            start_command[host].extend(self.get_node_start_commands(node_idx))
            pids[node_idx] = len(start_command[host]) - 1
            node['status'] = NodeStatus.STARTING
        log_print(f"Start {self.name.title()} node(s): {nodes_to_start}")
        result = self.ssh.exec(start_command)
        for node_idx, node in self.nodes.items():
            host = node['host']
            try:
                node['PID'] = int(result[host][pids[node_idx]].strip())
                if not node['PID']:
                    raise ValueError(f'no PID for node {node_idx}')
            except ValueError or IndexError or KeyError as e:
                raise TidenException(f"Can't start {self.name.title()} node {node_idx} at host {host}")
        check_command = {}
        status = {}
        for node_idx, node in self.nodes.items():
            host = node['host']
            if host not in check_command:
                check_command[host] = []
            check_command[host].extend(self.get_node_check_commands(node_idx))
            status[node_idx] = len(check_command[host]) - 1
        result = self.ssh.exec(check_command)
        for node_idx, node in self.nodes.items():
            host = node['host']
            try:
                if result[host][status[node_idx]]:
                    node['status'] = NodeStatus.STARTED
            except IndexError or ValueError or KeyError as e:
                raise TidenException(f"Can't check {self.name.title()} node {node_idx} started at host {host}")
            log_print(f"{self.name.title()} node {node_idx} started on {host} with PID {node['PID']}")

    def start_node(self, node_idx):
        self.rotate_node_log(node_idx)
        node = self.nodes[node_idx]
        host = node['host']
        start_commands = self.get_node_start_commands(node_idx)
        start_command = {host: start_commands}
        node['status'] = NodeStatus.STARTING
        log_print(f"Start {self.name.title()} node(s): {[node_idx]}")
        result = self.ssh.exec(start_command)
        node['PID'] = int(result[host][len(start_commands) - 1].strip())
        check_commands = self.get_node_check_commands(node_idx)
        check_command = {host: check_commands}
        result = self.ssh.exec(check_command)
        if not result[host][0]:
            raise TidenException(f"Can't start {self.name.title()} node {node_idx} at host {host}")
        node['status'] = NodeStatus.STARTED
        log_print(f"{self.name.title()} node {node_idx} started on {host} with PID {node['PID']}")

    def get_node_check_commands(self, node_idx):
        return [
            'sleep 1; ps -p %d -f | grep java 2>/dev/null' % self.nodes[node_idx]['PID'],
        ]

    def get_node_start_commands(self, node_idx):
        commands = [
            'mkdir -p %s' % self.nodes[node_idx]['run_dir'],
        ]
        env = self.get_node_env(node_idx)
        if env:
            commands.extend([f'export {env_name}=\"{env_value}\"' for env_name, env_value in env.items()])
        commands.extend([
            'cd %s; nohup java %s -cp %s %s %s 1>%s 2>&1 & echo $!' % (
                self.nodes[node_idx]['run_dir'],
                self.get_node_jvm_options(node_idx),
                self.java_app_jar,
                self.class_name,
                self.get_node_args(node_idx),
                self.nodes[node_idx]['log'],
            ),
        ])
        return commands

    def get_node_env(self, node_idx):
        return {}

    def get_node_run_dir(self, mode, node_idx):
        return f"{self.java_app_home}/{self.name}.{mode}.{node_idx}"

    def get_env_jvm_options(self, mode='client'):
        if self.app_type in self.config['environment']:
            return self.config['environment'][self.app_type].get(f'{mode}_jvm_options', [])
        else:
            return self.config['environment'].get(f'{mode}_jvm_options', [])

    def get_node_jvm_options(self, node_idx):
        return ' '.join(self.jvm_options)

    def get_node_args(self, node_idx):
        return ''

    def check_requirements(self):
        self.require_artifact(self.artifact_name)
