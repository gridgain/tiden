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

from sys import stdout
from time import time, sleep

from tiden import log_put, log_print, TidenException
from tiden.apps import App, NodeStatus


class JavaApp(App):
    default_jvm_options = [
        '-server',
        '-Djava.net.preferIPv4Stack=true',
        '-Djava.net.preferIPv6Addresses=false',
    ]
    class_name = ''
    start_timeout = 5

    java_app_jar = None
    java_app_home = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_timeout = self.__class__.start_timeout
        self.jvm_options = self.__class__.default_jvm_options.copy()
        self.class_name = self.__class__.class_name

    def setup(self):
        super().setup()
        self.java_app_jar = self.config['artifacts'][self.name]['remote_path']
        self.java_app_home = "%s/%s" % (self.config['rt']['remote']['test_module_dir'], self.name)
        self.add_nodes()

    def add_nodes(self):
        for host in self.get_hosts():
            for node_idx in range(0, self.get_servers_per_host()):
                self.add_node(host)

    def add_node(self, host=None):
        node_idx = len(self.nodes)
        self.nodes[node_idx] = {
            'host': host,
            'status': NodeStatus.NEW,
            'run_dir': "%s/%s" % (self.java_app_home, "server.%d" % node_idx)
        }

    def rotate_node_log(self, node_idx):
        run_counter = 0 if 'run_counter' not in self.nodes[node_idx] else self.nodes[node_idx]['run_counter'] + 1
        self.nodes[node_idx].update({
            'run_counter': run_counter,
            'log': "%s/%s" % (self.remote_test_dir, "node.%d.%s.%d.log" % (node_idx, self.name, run_counter)),
        })

    def _print_wait_for(self, message, node_idxs, time, timeout, done):
        log_put(f"Waiting for '{message}' at nodes [{', '.join([str(node_id) for node_id in node_idxs])}], {time}/{timeout} sec")
        if done:
            stdout.flush()
            log_print('')

    def wait_for(
            self,
            condition=lambda x: True,
            action=lambda: None,
            timeout=30,
            interval=1,
            progress_ticks=4,
            progress=lambda t, done: None,
            failed=lambda x: False,
            success=lambda x: True
    ):
        start_time = time()
        end_time = start_time + timeout

        def _progress_seconds():
            return timeout - max(0, int(end_time - time()))

        i = 0
        progress(_progress_seconds(), False)
        try:
            while True:
                result = action()
                if condition(result):
                    return success(result)
                elif failed is not None and failed(result):
                    return False
                if time() > end_time:
                    return False
                sleep(interval)
                if progress and progress_ticks and i % progress_ticks == 0:
                    progress(_progress_seconds(), False)
                i += 1
        finally:
            if progress:
                progress(_progress_seconds(), True)

    def wait_message(self, message, nodes_idx=None, timeout=30):
        if nodes_idx is None:
            node_idxs = self.nodes.keys()
        elif isinstance(nodes_idx, int):
            node_idxs = [nodes_idx]
        else:
            node_idxs = [int(node_idx) for node_idx in nodes_idx]

        return self.wait_for(
            action=lambda: self.grep_log(*node_idxs, message={'remote_regex': message, 'local_regex': f'({message})'}),
            condition=lambda result: all([
                node_id in result and
                'message' in result[node_id] and
                result[node_id]['message'] == message
                for node_id in node_idxs
            ]),
            timeout=timeout,
            interval=2,
            progress_ticks=3,
            progress=lambda t, done: self._print_wait_for(message, node_idxs, t, timeout, done)
        )

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
            try:
                host = node['host']
                node['PID'] = int(result[host][pids[node_idx]].strip())
                if not node['PID']:
                    raise ValueError(f'no PID for node {node_idx}')
            except ValueError or IndexError or KeyError  as e:
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
            try:
                host = node['host']
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
        return [
            'mkdir -p %s' % self.nodes[node_idx]['run_dir'],
            'cd %s; nohup java %s -cp %s %s %s 1>%s 2>&1 & echo $!' % (
                self.nodes[node_idx]['run_dir'],
                self.get_node_jvm_options(node_idx),
                self.java_app_jar,
                self.class_name,
                self.get_node_args(node_idx),
                self.nodes[node_idx]['log'],
            ),
        ]

    def get_node_jvm_options(self, node_idx):
        return ' '.join(self.jvm_options)

    def get_node_args(self, node_idx):
        return ''

    def get_servers_per_host(self):
        if self.name in self.config['environment']:
            return int(self.config['environment'][self.name].get(f'{self.get_app_type()}s_per_host', 1))
        else:
            return int(self.config['environment'].get(f'{self.get_app_type()}s_per_host', 1))

    def check_requirements(self):
        self.require_artifact(self.name)

    def get_app_type(self):
        return 'client'

    def get_hosts(self):
        if self.name in self.config['environment']:
            return self.config['environment'][self.name].get(f'{self.get_app_type()}_hosts', [])
        else:
            return self.config['environment'].get(f'{self.get_app_type()}_hosts', [])
