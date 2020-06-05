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

from ..app import App
from ..appexception import AppException
from ..nodestatus import NodeStatus
from ...util import *


class ZooException(AppException):
    pass


class Zookeeper (App):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = get_logger('Zookeeper')

        # to support COPY constructor
        if len(args) == 1 and isinstance(args[0], Zookeeper):
            self.__dict__ = args[0].__dict__
        else:
            if self.config['artifacts'].get('zookeeper') is not None:

                if self.config['artifacts']['zookeeper'].get('remote_home'):
                    self.zookeeper_home = self.config['artifacts']['zookeeper']['remote_home']

                hosts = []
                if self.config['environment'].get('zookeeper_hosts') is not None:
                    hosts = self.config['environment']['zookeeper_hosts']
                if len(hosts) == 0:
                    hosts = self.config['environment'].get('client_hosts')

                if self.config['environment'].get('zookeeper_total_nodes') is not None:
                    zk_nodes_amount = self.config['environment'].get('zookeeper_total_nodes')
                else:
                    log_print('WARN: Could not find zookeeper_total_nodes in environment, so default value 3 '
                              'Zookeeper nodes will be used', color='red')
                    zk_nodes_amount = 3

                self.zk_ports_prefix = '218{}'
                for node_idx in range(1, zk_nodes_amount + 1):
                    host = hosts[node_idx % len(hosts)]
                    self.nodes[node_idx] = {
                        'host': host,
                        'state': NodeStatus.NEW,
                        'client_port': self.zk_ports_prefix.format(node_idx),
                        'zoo_configs': {
                            'zoo.cfg': {
                                    'path': None,
                                    'values': ['initLimit=5', 'syncLimit=2',
                                               'clientPort={}'.format(self.zk_ports_prefix.format(node_idx))]
                                },
                            'env.cfg': {
                                    'path': None,
                                    'values': ['ZOO_LOG4J_PROP=\"DEBUG,CONSOLE,ROLLINGFILE\"']
                                }
                            }
                    }
            else:
                raise ZooException('Zookeeper module could not be configured.\n'
                                   'Zookeeper artifacts are not set in config file.')

    def setup(self):
        self.deploy_zookeeper()

    def deploy_zookeeper(self):
        """
        1. Create zookeeper directory on every zookeeper host.
        2. Create symlinks from zookeeper artifact to zookeeper directory (we don't want to copy the files).
        :return:
        """
        self.zookeeper_home = '{}/zookeeper'.format(self.config['rt']['remote']['test_module_dir'])
        self.set_node_option('*', 'home', self.zookeeper_home)
        hosts = {val.get('host') for key, val in self.nodes.items()}

        log_print("Deploying Zookeeper on hosts {}, nodes count={}, zoo home={}"
                  .format(hosts, len(self.nodes), self.zookeeper_home), color='green')

        prepare_zoo = {}
        artifact_remote_path = self.config['artifacts']['zookeeper']['remote_path']
        for host in hosts:
            prepare_zoo[host] = [
                'mkdir -p {}'.format(self.zookeeper_home),
                'ls -1 {}'.format(artifact_remote_path)
            ]
            resp = self.ssh.exec(prepare_zoo)

            # Create symlink for zookeeper internal folders and files (we don't)
            symlink_source_dirs = [symlink_dir for symlink_dir in resp[host][1].split('\n')
                                   if symlink_dir and symlink_dir not in ['docs', 'src', 'dist-maven']]

            prepare_zoo[host] = []
            for symlink_dir in symlink_source_dirs:
                prepare_zoo[host].append(
                    'ln -s {ln_src}/{ln_dir} {ln_dst}/{ln_dir}'.format(
                        ln_dir=symlink_dir, ln_src=artifact_remote_path, ln_dst=self.zookeeper_home)
                )
            self.ssh.exec(prepare_zoo)

    @classmethod
    def get_config_types(cls):
        return {
            'server': 'zoo.tmpl.cfg'
        }

    def check_requirements(self):
        self.require_artifact('zookeeper')
        # self.require_environment('zookeeper')

    @deprecated
    def start_zookeeper(self):
        """
        This method is deprecated. Use stop method instead.
        :return:
        """
        self.start()

    def start(self):
        """
        Start Zookeeper server nodes
        :return: none
        """
        self._prepare_zk_configs()

        for node_id in self.nodes.keys():
            self.start_node(node_id)

        self.fill_node_role()
        log_print('Zookeeper started:\n{}'.format(repr(self)), color='green')

    def start_node(self, node_id):
        started = False

        if node_id not in self.nodes:
            log_print('Node id {} is not found in nodes\n{}'.format(node_id, self.nodes), color='red')
            return

        if self.nodes[node_id].get('state') in [NodeStatus.STARTED]:
            log_print('Node id {} is already started:\n{}'.format(node_id, self.nodes[node_id]), color='red')
            return

        start_cmd = "export ZOOCFGDIR={};cd {};bin/zkServer.sh start {}". \
            format(self._get_cfg_path(node_id), self.nodes[node_id]['home'], self.get_config('zoo.cfg', node_id)['path'])

        run_zookeeper = {
            self.nodes[node_id]['host']: [start_cmd]
        }
        log_print('Starting Zookeeper on host {}'.format(self.nodes[node_id]['host']), color='green')
        result = self.ssh.exec(run_zookeeper)
        log_print(result, color='debug')
        for line in result[self.nodes[node_id]['host']][0].split('\n'):
            if 'STARTED' in line:
                started = True
        if started:
            self.nodes[node_id]['PID'] = self.get_pid(node_id)
            self.nodes[node_id]['state'] = NodeStatus.STARTED
        else:
            raise ZooException('Could not start Zookeeper node {} on host {} using command: {}'.
                               format(node_id, self.nodes[node_id]['host'], run_zookeeper))

    @deprecated
    def stop_zookeeper(self):
        """
        This method is deprecated. Use stop method instead.
        Stop Zookeeper server nodes
        :return: none
        """
        self.stop()

    def stop(self):
        for node_id in self.nodes.keys():
            self.stop_node(node_id)

    def stop_node(self, node_id):
        """
        Stop Zookeeper server nodes
        :return: none
        """

        stop_cmd = "cd {};bin/zkServer.sh stop {}"\
            .format(self.nodes[node_id]['home'], self.get_config('zoo.cfg', node_id)['path'])
        stop_zookeeper_cmd = {
            self.nodes[node_id]['host']: [stop_cmd]
        }
        log_print('Stopping Zookeeper on host %s' % self.nodes[node_id]['host'], color='green')
        out = self.ssh.exec(stop_zookeeper_cmd)
        self.nodes[node_id]['state'] = NodeStatus.KILLED

    def kill_node(self, node_id):
        log_print('Killing zookeeper node {}'.format(node_id), color='debug')
        kill_command = {
            self.nodes[node_id]['host']: ['nohup kill -9 {} > /dev/null 2>&1'.format(self.nodes[node_id]['PID'])]
        }
        self.ssh.exec(kill_command)
        self.nodes[node_id]['state'] = NodeStatus.KILLED

    def _prepare_zk_configs(self):
        commands = {}
        for node_id in self.nodes.keys():
            self.reset_zookeeper_config(node_id)
            self.nodes[node_id]['home'] = self.zookeeper_home
            host = self.nodes[node_id]['host']
            conf_path = self._get_cfg_path(node_id)
            default_conf_path = '{}/conf'.format('/'.join(conf_path.split('/')[:-1]))

            if commands.get(host) is None:
                commands[host] = []

            # create folders data, logs in zookeeper home
            commands[host].append('mkdir -p {}'.format(conf_path))
            commands[host].append('mkdir -p {}'.format(self._get_log_path(node_id)))
            commands[host].append('cp {}/log4j.properties -p {}/'.format(default_conf_path, conf_path))

            # update zoo.cfg and env.cfg params
            self.update_zookeeper_config('zoo.cfg', {'path': '{}/zoo.cfg'.format(conf_path)}, node_id=node_id)
            self.update_zookeeper_config('env.cfg', {'path': '{}/java.env'.format(conf_path)}, node_id=node_id)

            self.update_zookeeper_config('zoo.cfg',
                                         ['dataDir={}'.format(conf_path), '{}'.format(self._get_servers_cfg())],
                                         node_id=node_id)

            self.update_zookeeper_config('env.cfg',
                                         ['ZOO_LOG_DIR=\"{}\"'.format(self._get_log_path(node_id))],
                                         node_id=node_id)
            # create myid file
            commands[host] += [
                'echo -e "{}" > {}/myid'.format(node_id, conf_path)
            ]

        self.ssh.exec(commands)
        self._write_config_file(['env.cfg', 'zoo.cfg'])

    def reset_zookeeper_config(self, node_id):
        """
        Restore zoo_config structure after between tests.
        :param node_id:
        :return:
        """
        zoo_configs = self.nodes[node_id]['zoo_configs']

        if zoo_configs.get('zoo.cfg') and zoo_configs.get('zoo.cfg').get('values'):
            zoo_configs['zoo.cfg']['values'] = ['initLimit=5', 'syncLimit=2',
                                                'clientPort={}'.format(self.zk_ports_prefix.format(node_id))]
        if zoo_configs.get('env.cfg') and zoo_configs.get('env.cfg').get('values'):
            zoo_configs['env.cfg']['values'] = ['ZOO_LOG4J_PROP=\"DEBUG,CONSOLE,ROLLINGFILE\"']

    def update_zookeeper_config(self, config_name, values, node_id=None, flush=False):
        """
        Update zoo.cfg or/and env.cfg files. Values could be in dict or list format.
        Examples:
        self.update_zookeeper_config('zoo.cfg', {'path': '{}/zoo.cfg'.format(conf_path)}, node_id=node_id)
        self.update_zookeeper_config('env.cfg', ['ZOO_LOG_DIR=\"some_value\"'], node_id=1)

        :param config_name: zoo.cfg or/and env.cfg
        :param values:  values in dict or list format.
        :param node_id: if set, config files only for this node would be changes. Otherwise - for all nodes.
        :param flush:   if set to True files would be replaced on remote server.
        :return:
        """
        nodes = self.nodes.keys() if not node_id else [node_id]

        for node_id in nodes:
            zoo_configs = self.nodes[node_id]['zoo_configs']

            if config_name in zoo_configs:
                if isinstance(values, dict):
                    zoo_configs.get(config_name).update(values)
                if isinstance(values, list):
                    zoo_configs[config_name]['values'] += values

                if flush:
                    self._write_config_file(config_name, node_id)
            else:
                raise ZooException('Config name {} is not allowed config. Allowed configs are: zoo.cfg, env.cfg'
                                   .format(config_name))

    def _write_config_file(self, config, node_id=None):
        """
        Write config file to remote host.
        :param config:
        :param node_id:
        :return:
        """
        nodes = self.nodes.keys() if not node_id else [node_id]

        for node_id in nodes:
            commands = {self.nodes[node_id]['host']: []}
            configs = config if isinstance(config, list) else [config]
            for current_config in configs:
                zoo_configs = self.nodes[node_id]['zoo_configs'][current_config]
                commands[self.nodes[node_id]['host']] +=\
                    ['echo -e "{}" > {}'.format('\n'.join(zoo_configs['values']), zoo_configs['path'])]
            self.ssh.exec(commands)

    def get_config(self, config_name, node_id):
        """
        Return the copy of config (zoo.cfg or env.cfg).

        :param config_name: zoo.cfg or env.cfg
        :param node_id:
        :return:
        """
        from copy import deepcopy
        if node_id in self.nodes:
            if config_name in self.nodes[node_id]['zoo_configs']:
                return deepcopy(self.nodes[node_id]['zoo_configs'][config_name])

    def get_pid(self, node_id):
        pid = None
        cat_cmd = "cat {}/zookeeper_server.pid".format(self._get_cfg_path(node_id))
        command = {
            self.nodes[node_id]['host']: [cat_cmd]
        }
        result = self.ssh.exec(command)
        for line in result[self.nodes[node_id]['host']][0].split('\n'):
            m = search('(\d+)', line)
            if m:
                pid = m.group(1)
        return pid

    def fill_node_role(self):
        """
        Get current zookeeper role - leader/follower and refill self.nodes[node]['mode']
        """
        for node in self.nodes.keys():
            get_mode_command = "echo stat | nc localhost {} | grep Mode | sed 's/Mode: //g'".format(
                self.nodes[node]['client_port'])
            out = self.ssh.exec_on_host(self.nodes[node]['host'], [get_mode_command])
            self.nodes[node]['role'] = ''.join(out[self.nodes[node]['host']]).split('\n')[0]

    def get_zookeeper_specific_role(self, role='leader'):
        """
        Search for specific role in zoo cluster, if not found - call assert
        :param role: role for searching
        :return: node id with getting role
        """
        for node_id in self.nodes.keys():
            if self.nodes[node_id]['role'] == role:
                return node_id
        raise ZooException('Zookeeper node with role {} does not found. All nodes: {}'.format(role, self.nodes))

    def run_zk_client_command(self, cmd, assert_result=None, node_id=None):
        run_on_nodes = self.nodes.keys() if not node_id else [node_id]

        for node in run_on_nodes:
            cli_cmd = "cd {}; bin/zkCli.sh {}".format(self.nodes[node]['home'], cmd)

            log_print('*** Running command {} using zkCli.sh on host {} ***'.format(
                cli_cmd, self.nodes[node]['host']), color='green')

            out = self.ssh.exec_on_host(self.nodes[node]['host'], (cli_cmd,))

            if assert_result:
                if assert_result in out[self.nodes[node]['host']][0]:
                    log_print("Success!", color='green')
                else:
                    log_print("Something wrong during command evaluation: {}".format(out[self.nodes[node]['host']][0]),
                              color='red')
            break

    def _get_servers_cfg(self):
        fmt_str = 'server.{idx}={host}:288{idx}:388{idx}'
        return '\n'.join(
            [fmt_str.format(idx=node_id, host=self.nodes[node_id]['host']) for node_id in self.nodes.keys()])

    def _get_cfg_path(self, node_id):
        return '{}/conf_{}'.format(self.nodes[node_id]['home'], node_id)

    def _get_log_path(self, node_id):
        return '{}/logs_zk_node_{}'.format(self.config['rt']['remote']['test_dir'], node_id)

    def _get_zkConnectionString(self):
        tmp_host_port = []
        for node_idx in self.nodes.keys():
            tmp_host_port.append('{}:{}'.format(self.nodes[node_idx]['host'], self.nodes[node_idx]['client_port']))
        return ','.join(tmp_host_port)

    def __repr__(self):
        repr_str = 'Current Zookeeper cluster:'
        for node_id in self.nodes.keys():
            shortened_ignite_home = '/'.join(['...'] + self.nodes[node_id].get('home').split('/')[-5:])
            if self.nodes[node_id].get('log') is None:
                shortened_node_log = 'None'
            else:
                shortened_node_log = '/'.join(['...'] + self.nodes[node_id]['log'].split('/')[-5:])

            repr_str += '\n### Node id {}  {} ###\n\thost: {}'.format(
                node_id, self.nodes[node_id].get('state'),
                self.nodes[node_id].get('host')
            )

            repr_str += '\n\tnode_id: {}; PID: {}; Client Port: {}; Role: {}'.format(node_id,
                                                                                self.nodes[node_id].get('PID'),
                                                                                self.nodes[node_id].get('client_port'),
                                                                                self.nodes[node_id].get('role'))
            repr_str += '\n\tlog: %s' % shortened_node_log
            repr_str += '\n\tignite_home: %s' % shortened_ignite_home
        return repr_str

