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

# from ..app import App
from ..nodestatus import NodeStatus
from ...util import log_print, log_put


class Yardstick:  # (App):

    def __init__(self, ignite):
        self.ignite = ignite
        self.driver_options = {
            '-nn': 1,
            '-b': 1,
            '-w': 30,
            '-d': 30,
            '-t': 64,
            '-j': 10,
            '-sm': 'PRIMARY_SYNC',
            '--client': ''
        }
        # Class path
        # Client work directory
        self.remote_home = None
        self.method_home = None
        self.module_home = None
        self.class_paths = []
        for lib_dir in ['libs', 'libs/ignite-spring', 'libs/ignite-indexing', 'benchmarks/libs', 'libs/yardstick']:
            self.class_paths.append("%s/%s/*" % (self.ignite.client_ignite_home, lib_dir))
        self.driver_hosts = self.ignite.config['environment']['client_hosts']  # Should be a set?
        self.drivers_count = len(
            self.driver_hosts * self.ignite.config['environment'].get('clients_per_host', 1)
        )
        self.cmd_args_str = None
        self.jvm_opts_str = None
        self.start_index = 50000
        self.warmup = None
        self.duration = None

    def configure(self, driver_options, jvm_opts, **kwargs):
        final_driver_options = self.driver_options.copy()
        final_driver_options.update(driver_options)
        # Client work directory
        self.remote_home = self.ignite.config['rt']['remote']['test_dir']
        self.method_home = self.ignite.config['rt']['remote']['test_dir']
        self.module_home = self.ignite.config['rt']['remote']['test_module_dir']
        self.warmup = final_driver_options['-w']
        self.duration = final_driver_options['-d']
        driver_options_str = ''
        for opt_name in final_driver_options.keys():
            driver_options_str += "%s %s " % (opt_name, final_driver_options[opt_name])
        # Construct command-line arguments for driver
        self.cmd_args_str = \
            "{driver_options}  " \
            "--config {test_module_dir}/benchmark.properties " \
            "--logsFolder {test_method_dir} " \
            "--currentFolder {test_method_dir} " \
            "--scriptsFolder {test_method_dir}/bin".format(
                driver_options=driver_options_str[:-1],
                test_module_dir=self.module_home,
                test_method_dir=self.method_home
            )

        self.jvm_opts_str = ' '.join(jvm_opts)
        # Take default jvm options for driver
        if self.ignite.config['environment'].get('client_jvm_options'):
            self.jvm_opts_str += " %s" % ' '.join(self.ignite.config['environment']['client_jvm_options'])
        log_print("Yardstick drivers jvm options: %s" % self.jvm_opts_str)
        log_print(self.ignite.config['rt']['remote']['test_dir'])
        # Suppress full paths for print
        log_print("Yardstick drivers benchmark arguments: %s" % self.cmd_args_str.replace(
            self.module_home,
            '<test_module_dir>',
            )
        )
        if kwargs.get('start_index'):
            self.start_index = int(kwargs.get('start_index'))

    def run(self):
        log_print("Yardstick benchmark, %s driver(s) starting" % self.drivers_count)
        client_cmds = {}
        driver_nodes = []
        for client in range(1, self.drivers_count+1):
            # Get next client host
            host = self.ignite.get_and_inc_client_host()
            # Find client node index
            node_index = self.start_index + client
            while self.ignite.nodes.get(node_index) is not None and node_index < 1999:
                node_index += 1
            driver_nodes.append(node_index)
            # Prepare path to log file and work directories for probes
            log_file_path = "%s/grid.%s.node.%s.0.log" % (self.remote_home, self.ignite.grid_name, node_index)
            output_dir = '%s/%s.%s' % (self.method_home, self.ignite.name, client)
            # Driver jvm options
            node_jvm_opts_str = "%s -DNODE_IP=%s -DCONSISTENT_ID=%s -DIGNITE_QUIET=false " % (
                self.jvm_opts_str,
                host,
                self.ignite.get_node_consistent_id(node_index))
            # Yardstick driver command line
            cmd = "cd {ignite_home}; " \
                  "nohup $JAVA_HOME/bin/java " \
                  "-cp {class_path} " \
                  "{node_jvm_options_str} " \
                  "org.yardstickframework.BenchmarkDriverStartUp " \
                  "--outputFolder {output_dir} " \
                  "{args} " \
                  "> {log_file_path} 2>&1 &".format(
                      ignite_home=self.ignite.client_ignite_home,
                      class_path=':'.join(self.class_paths),
                      node_jvm_options_str=node_jvm_opts_str,
                      output_dir=output_dir,
                      args=self.cmd_args_str,
                      log_file_path=log_file_path
                  )
            self.ignite.nodes[node_index] = {
                'host': host,
                'log': log_file_path,
                'run_counter': 0,
                'status': NodeStatus.STARTING
            }
            if not client_cmds.get(host):
                client_cmds[host] = [cmd]
            else:
                client_cmds[host].append(cmd)

        try:
            self.ignite.ssh.exec(client_cmds)
            self.ignite.wait_for_topology_snapshot(
                self.ignite.get_nodes_num('server'),
                self.drivers_count,
                '',
                skip_nodes_check=True
            )
            started_nodes = self.ignite.get_started_node_attrs()
            started_drivers_num = 0
            for node_idx in started_nodes.keys():
                self.ignite.nodes[node_idx].update(started_nodes[node_idx])
                if started_nodes[node_idx].get('PID') is not None:
                    self.ignite.nodes[node_idx]['status'] = NodeStatus.STARTED
                    # Client node has id that starts from 5000
                    if int(node_idx) >= 5000:
                        started_drivers_num += 1
            log_print("Yardstick benchmark, started drivers: %s/%s" % (started_drivers_num, self.drivers_count))
            log_print("Yardstick waiting for stopped drivers")
            self.ignite.wait_for_topology_snapshot(
                None,
                0,
                timeout=int(self.warmup + self.duration + 180),
                check_only_servers=True
            )
        finally:
            self.ignite.kill_nodes(*driver_nodes)
            for id in driver_nodes:
                del self.ignite.nodes[id]

    def draw_charts(self):
        log_print(f"Drawing charts for {self.ignite.name}...")

        test_dir = self.method_home
        ignite_home = self.ignite.client_ignite_home

        cmd = f"bash {ignite_home}/benchmarks/bin/jfreechart-graph-gen.sh -gm STANDARD -i {test_dir}/{self.ignite.name}.*"
        log_print(cmd, color='debug')
        cmds = {}
        for host in self.driver_hosts:
            if not cmds.get(host):
                cmds[host] = [cmd]
            else:
                cmds[host].append(cmd)

        outputs = self.ignite.ssh.exec(cmds)

        for host, out in outputs.items():
            log_print(f"{host}:")
            log_print(f"{''.join(out)}")
