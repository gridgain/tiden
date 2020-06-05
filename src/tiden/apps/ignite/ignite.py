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

from copy import deepcopy
from os import path, remove
from os.path import exists

from datetime import datetime
from itertools import cycle
from re import search
from time import sleep, time
from traceback import format_exc
from zipfile import ZipFile

from ..app import App
from ..appexception import MissedRequirementException
from ..nodestatus import NodeStatus
from ...sshpool import SshPool
from ...util import log_put, log_print, print_red, apply_tiden_functions, util_sleep_for_a_while
from ...tidenexception import TidenException
from ...report.steps import step
from .ignitecomponents import IgniteComponents


class Ignite(IgniteComponents, App):
    jvm_options = {
        'server': '-Djava.net.preferIPv4Stack=true',
        'client': '-Djava.net.preferIPv4Stack=true',
    }

    activation_timeout = 240

    client_host_index = 0

    # for unique_node_ports
    MAX_NODES_PER_HOST = 16

    _setup = False

    def __init__(self, *args, **kwargs):
        # print('Ignite.__init__')
        if len(args) == 1 and isinstance(args[0], Ignite):
            self.__dict__ = args[0].__dict__
        else:
            name, config, ssh = args[0], args[1], args[2]
            super(Ignite, self).__init__(name, config, ssh, **kwargs)

            self.add_node_data_log_parsing_mask(
                node_data_key='PID',
                remote_regex='PID: [0-9]\+',
                local_regex='PID: (\d+)\n',
                force_type='int',
            )
            self.add_node_data_log_parsing_mask(
                node_data_key='node_id',
                remote_regex='locNodeId=[0-9a-f\-]{36}\]',
                local_regex='locNodeId=([0-9a-f\-]{36})\]'
            )

            self.app_type = 'ignite'

            self.grid_name = kwargs.get('grid_name', '1')

            self.additional_grid_name = kwargs.get('additional_grid_name')

            # used by get_and_inc_client_host (used by SnapshotUtility)
            self.client_host_index = 0

            # used by piclient and utilities
            self.client_ignite_home = None

            self._parent_cls = kwargs.get('parent_cls', None)

    def set_grid_name(self, name):
        self.grid_name = name

    def set_additional_grid_name(self, additional_grid_name):
        self.additional_grid_name = additional_grid_name

    @classmethod
    def get_config_types(cls):
        """
        for AppConfigBuilder.build_config
        :return:
        """
        return {
            'server': 'server.tmpl.xml',
            'client': 'client.tmpl.xml'
        }

    def check_requirements(self):
        super().require_artifact('ignite')
        if not self.config['environment'].get('server_hosts') \
                and not self.config['environment'].get('client_hosts'):
            raise MissedRequirementException('No environment hosts for Ignite application found')

    def setup(self):
        assert not self._setup, "Ignite.setup() should not be called twice"
        self._setup = True
        self.do_callback('on_setup')

    def _update_ignite_artifact_config_symlinks(self, ignite_name, artifact_name):
        # Find directory list for symlinks for remote hosts
        ignite_artifact_config = self.config['artifacts'][artifact_name]

        if ignite_artifact_config.get('symlink_dirs'):
            return ignite_artifact_config

        ignite_artifact_config['symlink_dirs'] = []
        try:
            if ignite_artifact_config.get('path'):
                with ZipFile(ignite_artifact_config['path'], "r") as artifact_zip:
                    for member in artifact_zip.namelist():
                        path_elements = member.split('/')
                        if ((member.endswith('/') and len(path_elements) == 2) or
                            (len(path_elements) == 1 and not member.endswith('/') and not member.endswith(
                                '.sha256'))) and \
                                path_elements[0] not in ignite_artifact_config['symlink_dirs']:
                            ignite_artifact_config['symlink_dirs'].append(path_elements[0])
        except FileNotFoundError as e:
            print(str(e))
        return ignite_artifact_config

    def _set_symlinks(self, ignite_name, artifact_name):
        """
        Setting up symlinks for remote host
        """
        server_hosts = self.config['environment'].get('server_hosts', [])
        if self.config['environment'].get('{}_hosts'.format(ignite_name)):
            server_hosts = self.config['environment'].get('{}_hosts'.format(ignite_name))
        client_hosts = self.config['environment'].get('client_hosts', [])

        # Add nodes
        node_idx = self.get_start_server_idx()
        for server_host in server_hosts:
            for idx in range(0, int(self.config['environment'].get('servers_per_host', 1))):
                self._add_server_node(server_host, ignite_name, node_idx)
                node_idx += 1

        # Prepare symlinks commands
        ignite_artifact_config = self._update_ignite_artifact_config_symlinks(ignite_name, artifact_name)
        symlink_ignite = {}

        # Each server use its own ignite_home directory
        for server_host in server_hosts:
            # output = self.ssh.exec_on_host(server_host, ['ls -1 %s' % ignite_artifact_config['remote_path']])
            symlink_ignite[server_host] = []
            for node_idx in self.nodes.keys():
                if self.nodes[node_idx]['host'] == server_host:
                    server_ignite_home = self.get_server_ignite_home(ignite_name, node_idx)
                    symlink_ignite[server_host].append('mkdir -p %s' % server_ignite_home)
                    for symlink_dir in ignite_artifact_config['symlink_dirs']:
                        symlink_ignite[server_host].append(
                            'ln -s %s/%s %s/%s' % (
                                ignite_artifact_config['remote_path'],
                                symlink_dir,
                                server_ignite_home,
                                symlink_dir,
                            )
                        )
                    # files = [item for item in output[server_host][0].split('\n') if
                    #          item not in ignite_artifact_config['symlink_dirs']]
                    # for file in files:
                    #     symlink_ignite[server_host].append(
                    #         'ln -s %s/%s %s/%s' % (
                    #             ignite_artifact_config['remote_path'],
                    #             file,
                    #             server_ignite_home,
                    #             file,
                    #         )
                    #     )

        self.ssh.exec(symlink_ignite)
        symlink_ignite.clear()

        # All clients share same ignite_home directory
        self.client_ignite_home = self.get_client_ignite_home(ignite_name)

        for client_host in client_hosts:
            symlink_ignite[client_host] = ['mkdir -p %s' % self.client_ignite_home]
            for symlink_dir in ignite_artifact_config['symlink_dirs']:
                symlink_ignite[client_host].append(
                    'ln -s %s/%s %s/%s' % (
                        ignite_artifact_config['remote_path'],
                        symlink_dir,
                        self.client_ignite_home,
                        symlink_dir,
                    )
                )

        self.ssh.exec(symlink_ignite)

    def get_client_ignite_home(self, name):
        return '{}/{}.client'.format(self.config['rt']['remote']['test_module_dir'], name)

    def get_server_ignite_home(self, name, index):
        return '{}/{}.server.{}'.format(self.config['rt']['remote']['test_module_dir'], name, index)

    def on_setup(self):
        # print('Ignite.on_setup')
        if self.is_static_inited:
            self.restore_nodes_config()
            self.client_ignite_home = self.get_client_ignite_home(self.name)
        else:
            self._set_symlinks(self.name, self.artifact_name)
            self._mark_scripts_executable('ignite')
        self.client_host_index = 0

    def set_node_option(self, node_filter, opt_name, opt_value):
        """
        Set option for node or node group
        :param node_filter: node index(es) or '*' for all nodes
        :param opt_name:    option name
        :param opt_value:   option value
        :return:
        """
        assert self._setup, "Ignite.setup() should be called before using set_node_option"
        node_filter = self.define_range(node_filter)
        for node_idx in sorted(self.nodes.keys()):
            if node_filter == '*' or node_idx in node_filter:
                self.nodes[node_idx].update({opt_name: opt_value})
                if opt_name == 'jvm_options' and self.config['environment'].get('server_jvm_options'):
                    if not set(self.config['environment']['server_jvm_options']) < set(
                            self.nodes[node_idx]['jvm_options']):
                        self.nodes[node_idx]['jvm_options'].extend(
                            self.config['environment']['server_jvm_options']
                        )

    def set_jvm_options(self, *args):
        if len(args) >= 1:
            self.jvm_options['server'] = args[0]
        if len(args) == 2:
            self.jvm_options['client'] = args[1]

    def set_activation_timeout(self, timeout):
        self.activation_timeout = timeout

    def make_node_log(self, node_idx):
        assert self._setup, "Ignite.setup() should be called before using make_node_log"
        self.nodes[node_idx]['log'] = '%s/grid.%s.node.%s.%s.log' % (
            self.config['rt']['remote']['test_dir'],
            self.grid_name,
            node_idx,
            self.nodes[node_idx]['run_counter']
        )

    def get_node_consistent_id(self, node_idx):
        # node's consistent id should not contains symbols that cannot be created in filesystem
        # otherwise this method cannot be used to get work/db/{consistentID} directory
        if node_idx is not None:
            if self.additional_grid_name:
                return 'node_%s_%d' % (self.additional_grid_name, node_idx)
            elif self.grid_name:
                return 'node_%s_%d' % (self.grid_name, node_idx)
            else:
                return 'node_%d' % (node_idx)
        else:
            return 'none'

    def get_base_disco_port(self):
        return 47500

    def get_base_communication_port(self):
        return 47100

    def get_node_communication_port(self, node_idx):
        if self.is_default_node(node_idx):
            return \
                int(node_idx) + \
                self.get_base_communication_port() - 1
        elif self.is_additional_node(node_idx):
            return \
                int(node_idx) + \
                self.get_base_communication_port() - 1 - self.ADDITIONAL_NODE_START_ID + self.MAX_NODES_PER_HOST / 4
        elif self.is_client_node(node_idx):
            return \
                int(node_idx) + \
                self.get_base_communication_port() - 1 - self.CLIENT_NODE_START_ID + 2 * (
                        self.MAX_NODES_PER_HOST / 4)
        elif self.is_common_node(node_idx):
            return \
                int(node_idx) + \
                self.get_base_communication_port() - 1 - self.COMMON_NODE_START_ID + 3 * (
                        self.MAX_NODES_PER_HOST / 4)
        else:
            return 0

    @staticmethod
    def define_range(range_to):
        if range_to is None:
            return ()
        # Leave star alone
        if range_to == '*':
            return range_to

        if isinstance(range_to, int):
            range_to = (range_to,)
        else:
            range_to = tuple(range_to)
        return range_to

    @step('Start {node_id} node')
    def start_node(self, node_id, force=False, **kwargs):
        """
        Start Ignite server node
        :param node_id:
        :param force: set to True if you need skip the check if node started
        :return:
        """
        assert self._setup, "Ignite.setup() should be called before using start_node"
        if not self.is_default_node(node_id):
            log_print('WARN: You can\'t use ID greater than %d as it used for other nodes.' %
                      self.ADDITIONAL_NODE_START_ID)
            return

        if self.nodes.get(node_id) and self.nodes[node_id]['status'] == NodeStatus.STARTED:
            if force:
                self.nodes[node_id]['run_counter'] += 1
                self.make_node_log(node_id)
            else:
                log_print('WARN: Node already started! You can\'t start it twice.')
                return

        self.nodes[node_id]['status'] = NodeStatus.STARTING

        server_num = len(self.get_alive_default_nodes()) + len(self.get_alive_additional_nodes())
        commands = {}
        node_start_line = "cd %s; " \
                          "nohup " \
                          "  bin/ignite.sh " \
                          "     %s " \
                          "     -v " \
                          "     %s " \
                          "     -J-DNODE_IP=%s " \
                          "     -J-DNODE_COMMUNICATION_PORT=%d " \
                          "     -J-DCONSISTENT_ID=%s " \
                          "> %s 2>&1 &"

        node_jvm_options = ''
        for jvm_opt in self.nodes[node_id]['jvm_options']:
            node_jvm_options += "-J%s " % jvm_opt

        self.nodes[node_id]['run_counter'] += 1
        self.make_node_log(node_id)

        node_jvm_options = apply_tiden_functions(
            node_jvm_options,
            filename="%s/%s" % (self.config['rt']['remote']['test_dir'], time()),
            test_dir=self.config['rt']['remote']['test_dir'],
            grid_name=str(self.grid_name),
            node_id=str(node_id),
            suite_var_dir=self.config['remote']['suite_var_dir'],
            run_counter=str(self.nodes[node_id]['run_counter']),
        )

        commands[self.nodes[node_id]['host']] = [node_start_line % (
            self.nodes[node_id]['ignite_home'],
            self.nodes[node_id]['config'],
            node_jvm_options,
            self.nodes[node_id]['host'],
            self.get_node_communication_port(node_id),
            self.get_node_consistent_id(node_id),
            self.nodes[node_id]['log']
        )]

        log_print('Start node %s' % node_id, color='blue')
        self.logger.debug(commands)
        self.ssh.exec(commands)

        if not kwargs.get('skip_topology_check', False):
            self.wait_for_topology_snapshot(
                server_num + 1 + kwargs.get('starting_nodes', 0),
                None,
                '',
                **kwargs,
            )

            self.update_started_node_status(node_id)

    def update_started_node_status(self, node_id):
        self.update_starting_node_attrs()
        self.nodes[node_id]['status'] = NodeStatus.STARTED
        self.dump_nodes_config(strict=False)

    def _get_start_node_commands(self, idx, **kwargs):
        node = self.nodes[idx]
        if not node['config'].startswith('/'):
            node['config'] = "{}/{}".format(self.config['rt']['remote']['test_module_dir'], node['config'])

        node_start_line = "cd {home_path}; " \
                          "nohup " \
                          "  bin/ignite.sh " \
                          "     {config_path} " \
                          "     -v " \
                          "     {jvm_options_str} " \
                          "     -J-DNODE_IP={node_ip} " \
                          "     -J-DNODE_COMMUNICATION_PORT={port} " \
                          "     -J-DCONSISTENT_ID={consistent_id} " \
                          "> {log_path} 2>&1 &"

        node_jvm_options = ''
        for jvm_opt in node['jvm_options']:
            node_jvm_options += f"-J{jvm_opt} "
        self.nodes[idx]['run_counter'] += 1
        self.make_node_log(idx)
        node_jvm_options = apply_tiden_functions(
            node_jvm_options,
            filename="{}/{}".format(self.config['rt']['remote']['test_dir'], time()),
            test_dir=self.config['rt']['remote']['test_dir'],
            grid_name=str(self.grid_name),
            node_id=str(idx),
            suite_var_dir=self.config['remote']['suite_var_dir'],
            run_counter=str(self.nodes[idx]['run_counter']),
        )
        commands = {
            node['host']: [
                node_start_line.format(
                    home_path=node['ignite_home'],
                    config_path=node['config'],
                    jvm_options_str=node_jvm_options,
                    node_ip=node['host'],
                    port=self.get_node_communication_port(idx),
                    consistent_id=self.get_node_consistent_id(idx),
                    log_path=node['log']
                )
            ]
        }
        self.nodes[idx]['status'] = NodeStatus.STARTING
        return commands

    def start_nodes(self, *args, **kwargs):
        """
        Start Ignite server nodes
        :return: none
        """
        assert self._setup, "Ignite.setup() should be called before using start_nodes"

        already_nodes = int(kwargs.get('already_nodes', 0))

        # first start nodes (either all grid or specific ones)
        if len(args) > 0:
            started_ids = []

            if kwargs.get('force', False):
                for node_id in args:
                    if node_id in self.nodes:
                        self.nodes[node_id]['status'] = NodeStatus.KILLED
                    else:
                        log_print('Could not find node with ID={}'.format(node_id), color='red')

            nodes_to_start = [
                node_id for node_id in args
                if self.nodes[node_id]['status'] in [NodeStatus.NEW, NodeStatus.KILLED, NodeStatus.KILLING]
            ]
            server_num = len(self.get_alive_default_nodes() + self.get_alive_additional_nodes())
            commands = {}
            for node_idx in nodes_to_start:
                node_start_commands = self._get_start_node_commands(node_idx, **kwargs)
                node_host = self.nodes[node_idx]['host']
                if node_host not in commands:
                    commands[node_host] = []
                commands[node_host].append(node_start_commands[node_host][0])

                server_num += 1
                started_ids.append(node_idx)

            if commands:
                log_print("Start grid '%s' node(s): %s" % (self.grid_name, nodes_to_start))
                self.ssh.exec(commands)

                self.wait_for_topology_snapshot(
                    server_num + already_nodes,
                    None,
                    '',
                    **kwargs,
                )
        else:
            assert len(self.get_alive_default_nodes() + self.get_alive_additional_nodes()) == 0, \
                "Ignite.start_nodes() supposes grid is not started"

            coord_node_idx = self.get_start_server_idx()
            started_ids = [coord_node_idx, ]
            coord_host = self.nodes[coord_node_idx]['host']
            # Start coordinator
            log_print("Start coordinator '%s' on host %s" % (self.get_node_consistent_id(coord_node_idx), coord_host))
            self.ssh.exec(self._get_start_node_commands(coord_node_idx, **kwargs))

            self.wait_for_topology_snapshot(
                1 + already_nodes,
                None,
                ", host %s" % coord_host,
                **kwargs,
            )

            server_num = 1

            # start all nodes except coordinator
            nodes_to_start = self.get_all_default_nodes()
            nodes_to_start.remove(coord_node_idx)

            disable_host_list = kwargs.get('disable_host_list')

            if disable_host_list:
                new_nodes_to_start = []
                for node in nodes_to_start:
                    node_hosts = self.nodes[node]['host']
                    if node_hosts not in disable_host_list:
                        new_nodes_to_start.append(node)
                nodes_to_start = new_nodes_to_start

            commands = {}
            for node_idx in nodes_to_start:
                node_start_commands = self._get_start_node_commands(node_idx, **kwargs)
                node_host = self.nodes[node_idx]['host']
                if node_host not in commands:
                    commands[node_host] = []
                commands[node_host].append(node_start_commands[node_host][0])

                server_num += 1
                started_ids.append(node_idx)

            if commands:
                log_print("Start grid '%s' node(s): %s" % (self.grid_name, nodes_to_start))
                self.ssh.exec(commands)

                self.wait_for_topology_snapshot(
                    server_num + already_nodes,
                    None,
                    '',
                    **kwargs,
                )

        # update attributes for started nodes
        if started_ids:
            self.update_starting_node_attrs()
            self.update_nodes_status(started_ids)
        self.dump_nodes_config(strict=False)

    @step('Start additional {range_nodes} nodes')
    def start_additional_nodes(self, range_nodes, **kwargs):
        """
        Starts additional nodes in defined range

        :param range_nodes: could be range of node IDs or single ID
        :return:
        """
        assert self._setup, "Ignite.setup() should be called before using start_additional_nodes"
        range_nodes = self.define_range(range_nodes)
        skipped_ids = []
        started_ids = []
        for node_idx in range_nodes:
            if not self.is_additional_node(node_idx):
                print('Additional nodes range is incorrect. Should be in range (%s, %s).' %
                      (self.ADDITIONAL_NODE_START_ID, self.COMMON_NODE_START_ID))

            if self.nodes[node_idx]['status'] == NodeStatus.STARTED:
                print('Node with id %s already started. Adding to skipping list' % node_idx)
                skipped_ids.append(node_idx)

        node_start_line = "cd %s; " \
                          "nohup " \
                          "  bin/ignite.sh " \
                          "    %s " \
                          "    -v " \
                          "    %s " \
                          "    -J-DNODE_IP=%s " \
                          "    -J-DNODE_COMMUNICATION_PORT=%d " \
                          "    -J-DCONSISTENT_ID=%s " \
                          "> %s 2>&1 &"

        commands = {}
        server_num = 0
        for node_idx in range_nodes:
            if node_idx not in skipped_ids:
                self.nodes[node_idx]['status'] = NodeStatus.STARTING
                self.nodes[node_idx]['run_counter'] += 1
                if 'config' not in self.nodes[node_idx] or not self.nodes[node_idx]['config'].startswith('/'):
                    self.nodes[node_idx]['config'] = "%s/%s" % (
                        self.config['rt']['remote']['test_module_dir'],
                        self.nodes[node_idx]['config']
                    )

                self.make_node_log(node_idx)

                node_jvm_options = " ".join(
                    map(lambda x: "-J%s" % x,
                        self.nodes[node_idx]['jvm_options']))

                node_jvm_options = apply_tiden_functions(
                    node_jvm_options,
                    filename="%s/%s" % (self.config['rt']['remote']['test_dir'], time()),
                    test_dir=self.config['rt']['remote']['test_dir'],
                    grid_name=str(self.grid_name),
                    node_id=str(node_idx),
                    suite_var_dir=self.config['remote']['suite_var_dir'],
                    run_counter=str(self.nodes[node_idx]['run_counter']),
                )

                host = self.nodes[node_idx]['host']
                if host not in commands:
                    commands[host] = []

                commands[host].append(
                    node_start_line % (
                        self.nodes[node_idx]['ignite_home'],
                        self.nodes[node_idx]['config'],
                        node_jvm_options,
                        host,
                        self.get_node_communication_port(node_idx),
                        self.get_node_consistent_id(node_idx),
                        self.nodes[node_idx]['log'],
                    )
                )
                server_num += 1
                started_ids.append(node_idx)

        if len(list(range_nodes)) > 1:
            log_print('Starting additional nodes %s' % ', '.join([str(n) for n in range_nodes]), color='blue')
        else:
            log_print('Starting additional node %s' % str(list(range_nodes)[0]), color='blue')

        self.ssh.exec(commands)

        if not kwargs.get('skip_topology_check'):
            if kwargs.get('client_nodes'):
                self.wait_for_topology_snapshot(
                    len(self.get_alive_default_nodes()),
                    server_num + kwargs.get('already_started', 0),
                    '',
                    **kwargs,
                )
            else:
                self.wait_for_topology_snapshot(
                    len(self.get_alive_default_nodes()) + len(self.get_alive_additional_nodes()) + server_num,
                    None,
                    '',
                    **kwargs,
                )

            self.update_starting_node_attrs()
            self.update_nodes_status(started_ids)
            self.dump_nodes_config(strict=False)

    def add_additional_nodes(self, config=None, num_nodes=1, **kwargs):
        """
        Adding additional nodes into existing cluster
        Node IDs starts with ADDITIONAL_NODE_START_ID

        :param config: config of added nodes
        :param num_nodes: number of nodes
        :param kwargs:
              name (optional) - ignite artifact name
        :return: range of newly added additional nodes
        """
        assert self._setup, "Ignite.setup() should be called before using add_additional_nodes"
        node_index = self.ADDITIONAL_NODE_START_ID + 1
        while self.nodes.get(node_index) is not None and node_index < self.COMMON_NODE_START_ID:
            node_index += 1
        range_to = range(node_index, node_index + num_nodes)

        ignite_name = self.name
        if kwargs.get('name') and kwargs['name']:
            ignite_name = kwargs['name']
        artifact_name = self.artifact_name
        if kwargs.get('artifact_name') and kwargs['artifact_name']:
            artifact_name = kwargs['artifact_name']

        server_hosts = self.config['environment']['server_hosts']
        if kwargs.get('server_hosts'):
            server_hosts = kwargs['server_hosts']
        cycle_hosts = cycle(server_hosts)

        cmd = {}
        env = self.config['environment']
        remote_test_module_dir = self.config['rt']['remote']['test_module_dir']
        for idx in range_to:
            host = next(cycle_hosts)
            ignite_home = '%s/%s.server.%s' % (remote_test_module_dir, ignite_name, idx)
            self.nodes[idx] = {
                'host': host,
                'ignite_home': ignite_home,
                'run_counter': -1,
                'status': NodeStatus.NEW,
            }
            self.nodes[idx]['jvm_options'] = []
            if env.get('server_jvm_options'):
                self.nodes[idx]['jvm_options'].extend(
                    env['server_jvm_options']
                )
            if kwargs.get('jvm_options'):
                self.nodes[idx]['jvm_options'].extend(
                    kwargs.get('jvm_options')
                )
            self.nodes[idx]['config'] = "%s/%s" % (
                remote_test_module_dir,
                config
            )
            if host not in cmd:
                cmd[host] = []
            cmd[host].append('mkdir -p %s' % ignite_home)
            artifact_cfg = self.config['artifacts'][artifact_name]
            for symlink_dir in artifact_cfg['symlink_dirs']:
                cmd[host].append(
                    'ln -s %s/%s %s/%s' % (
                        artifact_cfg['remote_path'],
                        symlink_dir,
                        ignite_home,
                        symlink_dir,
                    )
                )
        self.ssh.exec(cmd)

        return list(range_to)

    def update_starting_node_attrs(self):
        node_attrs = self.get_started_node_attrs()
        for node_id in node_attrs.keys():
            self.nodes[node_id].update(node_attrs[node_id])

    def check_node_status(self, node_id):
        host = self.nodes[node_id]['host']

        node_alive = False

        if 'PID' in self.nodes[node_id]:
            pid = self.nodes[node_id]['PID']

            cmd = "jps | grep %s | wc -l" % pid

            results = self.ssh.exec_on_host(host, (cmd, ))

            node_alive = '1' in results[host][0]

        if not node_alive:
            self.nodes[node_id]['status'] = NodeStatus.KILLED
            self.kill_node(node_id)

        return node_alive

    def update_nodes_status(self, started_ids):
        for node_idx in started_ids:
            if 'PID' in self.nodes[node_idx]:
                self.nodes[node_idx]['status'] = NodeStatus.STARTED
                if self.is_default_node(node_idx) or self.is_additional_node(node_idx):
                    node_type = 'server'
                else:
                    node_type = 'client'
                log_print(
                    "Ignite %s %s JVM started on %s with PID %s " % (
                        node_type,
                        node_idx,
                        self.nodes[node_idx]['host'],
                        self.nodes[node_idx]['PID']
                    )
                )

    @step('Kill {node_idx} node')
    def kill_node(self, node_idx, ignore_exceptions=False):
        if self.nodes.get(node_idx):
            if self.nodes[node_idx].get('PID'):
                self.nodes[node_idx]['status'] = NodeStatus.KILLING
                node_type = "node" if not self.is_additional_node(node_idx) else "additional node"
                log_print(f'Kill {node_type} {node_idx}', color='blue')
                kill_command = {
                    self.nodes[node_idx]['host']: ['nohup kill -9 %s > /dev/null 2>&1' % self.nodes[node_idx]['PID']]
                }
                try:
                    self.ssh.exec(kill_command)
                except:
                    if ignore_exceptions:
                        log_print(format_exc(), color='red')
                    else:
                        raise
                self._delete_server_node(node_idx)
            else:
                log_print('There is no PID for node %s' % node_idx, color='red')
        else:
            log_print('No node %s in the grid' % node_idx, color='red')

    def wait_for_messages_in_log(self, node_id, pattern, lines_limit=1000, timeout=200, interval=2, fail_pattern=None):
        log, host = self.nodes.get(node_id, {}).get('log'), self.nodes.get(node_id).get('host')
        end_time = time() + timeout
        while time() < end_time:
            output = self.ssh.exec({host: [f'cat {log} | tail -n {lines_limit} | grep "{pattern}"']})
            if output[host][0]:
                return output[host][0]
            if fail_pattern:
                fail_output = self.ssh.exec({host: [f'cat {log} | tail -n {lines_limit} | grep "{fail_pattern}"']})
                if fail_output[host][0]:
                    raise TidenException('Found fail pattern in logs')
            util_sleep_for_a_while(interval, msg=f'waiting for "{pattern}"')
        return ''

    def kill_node_on_message(self, node_idx):
        """
        Try to kill node with index node_idx during Checkpoint process. For that we generate IO load using StressT
        class to slow down node's process and checking 'Checkpoint started' message in the node's log tail. If message
        is found, then kill node. If not... get upset but kill it anyway.

        :param node_idx: node index you are trying to kill.
        :return:
        """

        if self.nodes.get(node_idx) and self.nodes.get(node_idx).get('PID'):
            # wait for checkpoint starting
            output = self.wait_for_messages_in_log(node_idx, 'Processing join discovery data',
                                                   interval=1)

            if not output:
                log_print('Msg is not found logs for node %s' % node_idx, color='red')

            self.kill_node(node_idx)
        else:
            log_print('No node %s in the grid' % node_idx, color='red')

    def kill_node_during_checkpoint(self, node_idx):
        """
        Try to kill node with index node_idx during Checkpoint process. For that we generate IO load using StressT
        class to slow down node's process and checking 'Checkpoint started' message in the node's log tail. If message
        is found, then kill node. If not... get upset but kill it anyway.

        :param node_idx: node index you are trying to kill.
        :return:
        """
        from tiden.stress import StressT
        from tiden.util import util_get_now

        make_stress = StressT(self.ssh)

        if self.nodes.get(node_idx) and self.nodes.get(node_idx).get('PID'):
            path, host = self.nodes.get(node_idx).get('ignite_home'), self.nodes.get(node_idx).get('host')
            log_print('Going to load IO for 120 sec. Started at %s' % util_get_now(), color='green')
            make_stress.fio_start(120, path, host)

            util_sleep_for_a_while(5)
            # wait for checkpoint starting
            output = self.wait_for_messages_in_log(node_idx, "Checkpoint started", lines_limit=10)

            if not output:
                log_print('Checkpoint has not found in logs for node %s' % node_idx, color='red')

            self.kill_node(node_idx)

            make_stress.fio_rm_file(path, host)
        else:
            log_print('No node %s in the grid' % node_idx, color='red')

    def stop_nodes(self, force=False):
        """
        Stop all server nodes
        :return:
        """
        log_print('Stop nodes')
        alive_nodes = self.get_alive_additional_nodes() + self.get_alive_default_nodes()
        server_num = len(alive_nodes)
        log_put("Stop grid: running server nodes: %s/%s" % (str(server_num), str(server_num)))
        # self.ssh.killall('java')
        commands = {}
        ignite_pids = []

        kill_command = "kill -9 %s" if force else "kill %s"
        for node_idx in alive_nodes:
            if 'PID' not in self.nodes[node_idx] or self.nodes[node_idx]['PID'] is None:
                print_red("Trying to kill node %s without PID" % str(node_idx))
                continue

            node_idx_host = self.nodes[node_idx]['host']
            if commands.get(node_idx_host) is None:
                commands[node_idx_host] = []
            commands[node_idx_host].append(kill_command % str(self.nodes[node_idx]['PID']))
            ignite_pids.append(self.nodes[node_idx]['PID'])
            self.nodes[node_idx]['status'] = NodeStatus.KILLING

        self.logger.debug(commands)
        self.logger.debug(ignite_pids)
        self.ssh.exec(commands)
        started = int(time())
        timeout_counter = 0
        running_num = server_num
        while timeout_counter < self.snapshot_timeout and running_num > 0:
            java_processes = self.ssh.jps()
            running_pids = [java_process for java_process in java_processes
                            if int(java_process['pid']) in ignite_pids]
            running_num = len(running_pids)

            for node_index in alive_nodes:
                pid = 0
                if 'PID' in self.nodes[node_index] and self.nodes[node_index]['PID'] is not None:
                    pid = self.nodes[node_index]['PID']
                if pid > 0 and pid not in running_pids:
                    self._delete_server_node(node_index)

            log_put("Stop grid: running server nodes: %s/%s" % (running_num, str(server_num)))
            timeout_counter = int(time()) - started
            sleep(5)

        log_print()
        if running_num == 0:
            log_print("%s server node(s) stopped" % str(server_num))
        else:
            log_print("%s/%s server node(s) NOT stopped" % (str(running_num), str(server_num)), color='red')

        return running_num

    def _add_server_node(self, server_host, ignite_name, node_idx):
        server_ignite_home = self.get_server_ignite_home(ignite_name, node_idx)

        self.nodes[node_idx] = {
            'host': server_host,
            'ignite_home': server_ignite_home,
            'run_counter': -1,
            'status': NodeStatus.NEW,
            'template_variables': {
                'consistent_id': self.get_node_consistent_id(node_idx)
            }
        }
        self.nodes[node_idx]['jvm_options'] = []
        if self.config['environment'].get('server_jvm_options'):
            self.nodes[node_idx]['jvm_options'].extend(
                self.config['environment']['server_jvm_options']
            )

    def _delete_server_node(self, node_index):
        if not self.is_client_node(node_index):
            if 'PID' in self.nodes[node_index]:
                del self.nodes[node_index]['PID']
            if 'rest_port' in self.nodes[node_index]:
                del self.nodes[node_index]['rest_port']
            if 'binary_rest_port' in self.nodes[node_index]:
                del self.nodes[node_index]['binary_rest_port']
            if 'status' in self.nodes[node_index]:
                self.nodes[node_index]['status'] = NodeStatus.KILLED
            # if self.nodes[node_index].get('node_id') is not None:
            #     del self.nodes[node_index]['node_id']
            # print_blue(self.nodes[node_index])

    def find_exception_in_logs(self, exception, host_group='server', result_node_option='exception', default_value=''):
        self.get_data_from_log(
            host_group,
            '%s' % exception,
            '(%s)' % exception,
            result_node_option,
            default_value=default_value
        )
        exceptions_cnt = 0
        for node_idx in self.nodes.keys():
            if result_node_option in self.nodes[node_idx] and \
                    self.nodes[node_idx][result_node_option] is not None and \
                    self.nodes[node_idx][result_node_option] != default_value:
                exceptions_cnt = exceptions_cnt + 1
        return exceptions_cnt

    def get_data_from_log(self, host_group, grep_text, regex_match, node_option_name, **kwargs):
        """
        Grep node logs for data, populates self.nodes[node_option_name]
        :return:
        """
        commands = {}
        result_order = {}

        if 'default_value' in kwargs:
            default_value = kwargs['default_value']

            for node_idx in self.nodes.keys():
                self.nodes[node_idx][node_option_name] = default_value

        if 'server' == host_group:
            node_idx_filter = (self.get_all_additional_nodes() + self.get_all_default_nodes())
        elif 'client' == host_group:
            # TODO client_common_hosts
            node_idx_filter = (self.get_all_client_nodes() + self.get_all_common_nodes())
        # elif 'common' == host_group:
        #     node_idx_filter = (self.get_all_common_nodes())
        elif type(host_group) == type([]):
            node_idx_filter = host_group
        else:
            assert False, "Unknown host group!"

        for node_idx in node_idx_filter:
            node_idx_host = self.nodes[node_idx]['host']
            if 'log' in self.nodes[node_idx]:
                if commands.get(node_idx_host) is None:
                    commands[node_idx_host] = []
                    result_order[node_idx_host] = []
                commands[node_idx_host].append('grep "%s" %s' % (grep_text, self.nodes[node_idx]['log']))
                result_order[node_idx_host].append(node_idx)
            else:
                print_red('There is no log for node %s' % node_idx)

        results = self.ssh.exec(commands)

        for host in results.keys():
            for res_node_idx in range(0, len(results[host])):
                m = search(regex_match, results[host][res_node_idx])
                if m:
                    val = m.group(1)
                    if kwargs.get('force_type') == 'int':
                        val = int(val)
                    self.nodes[result_order[host][res_node_idx]][node_option_name] = val

    def get_and_inc_client_host(self, client_hosts=None):
        if client_hosts is None:
            client_hosts = self.config['environment']['client_hosts']
        if len(client_hosts) <= self.client_host_index:
            self.client_host_index = 0
        host = client_hosts[self.client_host_index]
        self.client_host_index += 1
        return host

    def get_client_host(self, client_hosts=None):
        if client_hosts is None:
            client_hosts = self.config['environment']['client_hosts']
        if len(client_hosts) <= self.client_host_index:
            return client_hosts[0]
        else:
            return client_hosts[self.client_host_index]

    def grep_in_node_log(self, node_id, grep_pattern):
        """
        Get data from node logs
        :return:
        """
        result = None
        if self.nodes.get(node_id):
            host = self.nodes[node_id]['host']
            commands = {
                host: [
                    'grep -E "%s" %s' % (grep_pattern, self.nodes[node_id]['log'])
                ]
            }
            results = self.ssh.exec(commands)
            log_print("Log grep output: %s" % results, 2)

            if results.get(host) is not None:
                if isinstance(results[host], list):
                    result = results[host][0]
                else:
                    result = results[host]
        else:
            log_print("Node with id=%s not found" % node_id, 2)

        return result

    def reset(self, hard=False):
        server_nodes = self.get_all_default_nodes() + self.get_all_additional_nodes()
        tmp_nodes = {}
        for node_idx in self.nodes.keys():
            if node_idx in server_nodes:
                if hard:
                    self._delete_server_node(node_idx)
                tmp_nodes[node_idx] = dict(self.nodes[node_idx])
                if tmp_nodes[node_idx].get('log'):
                    del tmp_nodes[node_idx]['log']
                tmp_nodes[node_idx]['run_counter'] = 0
        self.nodes = tmp_nodes

    def get_jvm_options(self, node_idx):
        return self.nodes[node_idx].get('jvm_options', [])

    def get_work_dir(self, node_id):
        if self.nodes.get(node_id):
            return self.nodes[node_id].get('ignite_home')
        else:
            return None

    def copy_work_dir_from(self, node_id, src_folder):
        log_print("Copy from source directory {} to Ignite working directory for node {}".format(src_folder, node_id),
                  color='debug')
        commands = {}
        nodes = self.nodes.keys() if not node_id else [node_id]
        for node_idx in nodes:
            host = self.nodes[node_idx]['host']
            cmd_str = 'rm -rf {}/work;cp -rf {}/work {}'. \
                format(self.nodes[node_idx]['ignite_home'], src_folder, self.nodes[node_idx]['ignite_home'])
            commands.setdefault(host, []).append(cmd_str)
        log_print(commands, color='debug')
        self.ssh.exec(commands)

    def cleanup_work_dir(self, node_id=None):
        log_put("Cleanup Ignite working directory ... ")
        commands = {}
        nodes = self.nodes.keys() if not node_id else [node_id]
        for node_idx in nodes:
            host = self.nodes[node_idx]['host']
            commands.setdefault(host, []).append('rm -rf %s/work/*' % self.nodes[node_idx]['ignite_home'])
        results = self.ssh.exec(commands)
        log_print(results)
        log_put("Ignite working directory deleted.")
        log_print()

    def __repr__(self):
        repr_str = 'Current cluster:'
        for node_id in self.nodes.keys():
            shortened_ignite_home = '/'.join(['...'] + self.nodes[node_id].get('ignite_home').split('/')[-5:])
            if self.nodes[node_id].get('log') is None:
                shortened_node_log = 'None'
            else:
                shortened_node_log = '/'.join(['...'] + self.nodes[node_id]['log'].split('/')[-5:])

            repr_str += '\n### Node id %s  %s ###\n\thost: %s;  config: %s' % (
                node_id, self.nodes[node_id].get('status'),
                self.nodes[node_id].get('host'),
                self.nodes[node_id].get('config')
            )

            repr_str += '\n\tnode_id: %s; PID: %s; JMX: %s; CommandPort: %s' % (self.nodes[node_id].get('node_id'),
                                                                                self.nodes[node_id].get('PID'),
                                                                                self.nodes[node_id].get('jmx_port'),
                                                                                self.nodes[node_id].get(
                                                                                    'binary_rest_port'))
            repr_str += '\n\tlog: %s' % shortened_node_log
            repr_str += '\n\tignite_home: %s' % shortened_ignite_home
        return repr_str

    def get_started_node_attrs(self):
        node_idxs = []
        for node_idx in self.nodes.keys():
            if self.nodes[node_idx].get('status') in [NodeStatus.STARTED, NodeStatus.STARTING]:
                node_idxs.append(node_idx)

        attrs = self.grep_log(*node_idxs, **self.get_log_masks())
        return attrs

    def stop_piclient(self, node_index, gracefully=False, clear=False):
        if gracefully:
            self.nodes[node_index]['gateway'].entry_point.shutdownGracefully()

        del self.nodes[node_index]['gateway_port']

        # Close connections and shutdown gateway
        self.nodes[node_index]['gateway'].shutdown()
        del self.nodes[node_index]['gateway']

        self.kill_node(node_index)

        if clear:
            del self.nodes[node_index]

    def get_pids(self, host_group):
        return self.get_data_from_log(
            host_group,
            'PID: [0-9]\+',
            'PID: (\d+)\n',
            'PID',
            force_type='int'
        )

    def get_jmx_port(self, host_group):
        return self.get_data_from_log(
            host_group,
            'JMX (remote: on, port: [0-9]\+,',
            'JMX \(remote: on, port: (\d+),',
            'jmx_port',
            force_type='int'
        )

    def run_on_all_nodes(self, command):
        output = dict()
        server_nodes = self.get_all_default_nodes() + self.get_all_additional_nodes()

        for node_id in server_nodes:
            commands = {}
            host = self.nodes[node_id]['host']
            ignite_home = self.nodes[node_id]['ignite_home']
            command_per_node = command.replace('__CONSISTENT_ID__', self.get_node_consistent_id(node_id))
            commands[host] = ['cd %s;%s' % (ignite_home, command_per_node)]
            log_print(commands, color='yellow')
            tmp_output = self.ssh.exec(commands)
            log_print(tmp_output, color='yellow')
            output[node_id] = tmp_output[host][0]

        log_print(output)

        return output

    def find_in_node_log(self, node_idx, pattern):
        if self.nodes.get(node_idx):
            log_file = self.nodes[node_idx].get('log')
            host = self.nodes[node_idx]['host']
            kill_command = {
                host: ['cat {} | {}'.format(log_file, pattern)]
            }
            output = self.ssh.exec(kill_command)
            if output[host][0] != '':
                log_print(output, color='debug')
                return True
            else:
                return False

    def find_fails(self, *node_ids,
                   files_to_check: list = None,
                   store_files=None,
                   time_pattern=r'\[(\d+:\d+:\d+)(,\d+|)\]|T(\d+:\d+:\d+)(\.\d+|)',
                   ignore_node_ids=False):
        """
        Download log files one by one
        Find fails in cluster logs and form it as dict

        :param node_ids:            custom nodes ids to search (all nodes by default)
        :param files_to_check:      path and host for file which needs to be checked
        :param store_files          directory where temp log files will be stored
        :param ignore_node_ids:     ignore all received node_ids parameters
        :return: dict               exception dict
                                    Example:
                                    {
                                      'node.1.1.log': {
                                         "exceptions": [
                                            {
                                               "line": 123,
                                               "exception": [
                                                  "Bad thin in log line #123\n",
                                                  "Bad thin in log line #124\n",
                                                  "Bad thin in log line #125\n",
                                                  ....
                                               ],
                                               "time": datetime.datetime(2020, X, X, X)
                                            }
                                         ],
                                         "body": [
                                            # all log
                                         ],
                                         "file": {
                                            "host": '172.25.1.XX',
                                            "log_path": "/storage/ssd/.../node.1.1.log",
                                            "node.1.1.log"
                                         }
                                      }
                                    }
        """
        # all nodes by default
        node_ids = [] if ignore_node_ids else list(node_ids) if node_ids else list(self.nodes.keys())

        if files_to_check is None:
            files_to_check = []

        for node_id, node in self.nodes.items():
            if node_id not in node_ids:
                continue
            files_to_check.append({
                'host': node['host'],
                'log_path': node["log"],
                'name': path.basename(node["log"])
            })

        local_files = []
        try:
            found_exceptions = {}
            for file_to_check in files_to_check:
                local_file_path = path.join(store_files, file_to_check['name'])
                local_files.append(local_file_path)
                self.ssh.download_from_host(file_to_check['host'], file_to_check['log_path'], local_file_path)
                with open(local_file_path, 'r') as f:
                    all_lines = f.readlines()
                    exception_list = self.find_exceptions_list(all_lines)
                    if exception_list:
                        found_exceptions[file_to_check['name']] = {
                            'file': file_to_check,
                            'exceptions': exception_list,
                            'body': all_lines
                        }

            now_time = datetime.now()
            format_date_now = f'{now_time.year}.{now_time.month}.{now_time.day}'
            for file_name, found_exception in deepcopy(found_exceptions).items():
                for ex_idx, exception_info in enumerate(found_exception['exceptions']):
                    time_is_found = False
                    for line in exception_info['exception']:
                        if found_exceptions[file_name]['exceptions'][ex_idx].get('time'):
                            break
                        found_time_str = search(time_pattern, line)
                        if found_time_str and (found_time_str.group(1) or found_time_str.group(3)):
                            time_is_found = True
                            found_time_str = found_time_str.group(1) or found_time_str.group(3)
                            found_time = datetime.strptime(f'{format_date_now} {found_time_str}', '%Y.%m.%d %H:%M:%S')
                            found_exceptions[file_name]['exceptions'][ex_idx]['time'] = found_time
                            break
                    if not time_is_found:
                        upper_line = exception_info['line'] - 1
                        for i in range(100):
                            if upper_line < 0:
                                break
                            upper_line -= 1
                            line_to_search = found_exception['body'][upper_line]
                            found_time_str = search(time_pattern, line_to_search)
                            if found_time_str and (found_time_str.group(1) or found_time_str.group(3)):
                                found_time_str = found_time_str.group(1) or found_time_str.group(3)
                                found_time = datetime.strptime(f'{format_date_now} {found_time_str}', '%Y.%m.%d %H:%M:%S')
                                found_exceptions[file_name]['exceptions'][ex_idx]['time'] = found_time
                                break
        finally:
            for file in local_files:
                if exists(file):
                    remove(file)
        return found_exceptions

    def find_exceptions_list(self, file_content,
                             start_line_patterns=None,
                             end_line_patterns=None):
        """
        Find all exceptions in file content and form it in list

        :param      file_content:           open('filepath').readlines()
        :param      start_line_patterns     re.compile(pattern) defined exception start line
        :param      end_line_patterns       re.compile(pattern) defined exception end line
        :return:    Example:
                    [
                       "line": 123,
                       "exception": [
                          "Bad thin in log line #123\n",
                          "Bad thin in log line #124\n",
                          "Bad thin in log line #125\n",
                          ....
                    ],
        """
        if start_line_patterns is None:
            start_line_patterns = re.compile(
                "^((Caused by:* )*class [a-zA-Z0-9\._]+Exception: "
                "|java.lang.NullPointerException"
                "|java.lang.[a-zA-Z0-9\._]+(Exception"
                "|Error): )"
                "|\] Fail"
                "|\] Critical"
                "|Error: Failed"
                "|\(err\) Failed"
                "|: Failed"
            )

        if end_line_patterns is None:
            end_line_patterns = re.compile(
                "\.\.\. \d+ more|"
                'at java\.lang\.Thread\.run\(Thread\.java:\d+\)|'
                'at org.apache.ignite.startup.cmdline.CommandLineStartup.main\(CommandLineStartup.java:\d+\)|'
                'at org\.apache\.ignite.spi.IgniteSpiThread\.run\(IgniteSpiThread\.java:\d+\)|'
                'at org\.apache\.ignite\.testtools\.SimpleIgniteTestClient\.main\(SimpleIgniteTestClient\.java:\d+\)'
            )

        exception_lines = []
        exception_list = []

        after_exception_end_line = False
        in_exception_section = False
        lines = file_content
        lines_count = len(lines)

        start_line = 0

        for line_idx, line in enumerate(lines):
            if in_exception_section:
                if search(end_line_patterns, line):
                    in_exception_section = False
                    after_exception_end_line = True
                    exception_lines.append(line.rstrip())
            else:
                # is start line
                if not search('\[WARNING\]', line) and search(start_line_patterns, line):
                    in_exception_section = True
                    if line.startswith('Caused by') and after_exception_end_line:
                        if len(exception_lines) > 0:
                            exception_lines = exception_lines[:-1]
                    else:

                        if exception_lines:
                            exception_list.append({
                                'line': start_line,
                                'exception': exception_lines
                            })
                        start_line = line_idx + 1
                        exception_lines = []

                after_exception_end_line = False
            if in_exception_section:
                exception_lines.append(line.rstrip())

            if line_idx == lines_count - 1:
                if exception_lines:
                    exception_list.append({
                        'line': start_line,
                        'exception': exception_lines
                    })

        return exception_list

    def get_run_info(self, test_run_info=None):
        run_info = self._get_run_info_from_log()
        if test_run_info:
            return self._merge_run_info(test_run_info, run_info)
        else:
            return run_info

    def _merge_run_info(self, test_run_info, app_run_info):
        for k, v in app_run_info.items():
            if k in test_run_info:
                if type(v) == type(0) or type(v) == type(0.0):
                    if v > test_run_info[k]:
                        test_run_info[k] = v
                else:
                    test_run_info[k] = v
            else:
                test_run_info[k] = v
        return test_run_info

    def check_node_is_alive(self, node_index):
        """
        Check if java process with PID from node is still running on host using jps utility.
        :param node_index:
        :return:
        """
        if node_index not in self.nodes:
            log_print('Could not find node with ID={}'.format(node_index), color='red')
            return False

        try:
            pid = int(self.nodes[node_index].get('PID'))
        except TypeError:
            assert False, "Something wrong happened. Cannot convert '{}' to pid=int() from node {}".format(
                self.nodes[node_index].get('PID'), self.nodes[node_index])
        assert pid is not None, "Something wrong happened. Cannot get 'PID' from node {}".format(self.nodes[node_index])

        jps = self.ssh.jps()
        alive_pids = [int(node['pid']) for node in jps]
        if pid > 0 and pid in alive_pids:
            return True
        return False

    def _get_run_info_from_log(self):
        """
        Get runtime information from ignite server nodes log:
         - caches number from node log. Grep with 'Started cache' | wc -l
         - servers, clients, CPU, heap, offheap from 'Topology snapshot' message.
        :return: dict with got parameters.
        """
        re_str = '\[ver=\d+,.*(servers)=(\d+), (clients)=(\d+),.*(CPUs)=(\d+),.*(offheap)=([0-9\.MBG]+)' \
                 '.*(heap)=([0-9\.MBG]+)\]'
        run_info = dict()

        try:
            # to handle situation when nodes could be restarted/failed and so on, we need to check all nodes
            for node_idx in self.get_all_default_nodes():
                command = []
                node_idx_host = self.nodes[node_idx]['host']
                if 'log' in self.nodes[node_idx]:
                    # get caches count
                    command.append('grep "{}" {} 2>/dev/null | '
                                   'grep -Eo "name=([^,]*)," 2>/dev/null | '
                                   'sort | uniq | wc -l'.format('Started cache', self.nodes[node_idx]['log']))
                    # get heap / offheap / CPU info
                    command.append('grep -A 1 "Topology snapshot" {} 2>/dev/null | '
                                   'grep -B 1 "=ACTIVE" 2>/dev/null | '
                                   'grep "Topology snapshot" 2>/dev/null '.format(self.nodes[node_idx]['log']))
                    output = self.ssh.exec_on_host(node_idx_host, command)
                    info = output[node_idx_host]

                    if len(info) != 2:
                        log_print('Returned info could not be parsed\n{}'.format(info), color='red')
                        continue

                    if int(info[0].strip('\n')) == 0:
                        continue

                    run_info['caches number'] = int(info[0].strip('\n'))

                    for node_data in info[1].split('\n'):
                        match = search(re_str, node_data)
                        if match:
                            skip_stat = False
                            for idx in range(1, 6):
                                # do not override max values
                                if run_info.get(match.group(2 * idx - 1)) and match.group(2 * idx - 1) in ['servers',
                                                                                                           'clients']:
                                    skip_stat = int(run_info.get(match.group(2 * idx - 1))) > int(match.group(2 * idx))
                                if skip_stat:
                                    continue
                                run_info[match.group(2 * idx - 1)] = match.group(2 * idx)

                else:
                    log_print('There is no log for node %s' % node_idx)
        except Exception as e:
            log_print('Some problem obtaining running Ignite stat info: %s' % str(e), color='red')
            pass

        return run_info

    def save_lfs(self, tag, dir_path=None, timeout=SshPool.default_timeout):
        """
        Copy Ignite LFS
        :param      tag:        name of tag, used for filename of zip archive
        :param      dir_path:   remote path of LFS zip archive
        :return:    None
        """
        log_print("Storing Ignite LFS to '%s' ... " % tag)
        if dir_path is None:
            dir_path = self.config['remote']['suite_var_dir']
        commands = {}
        started = time()
        for node_idx in self.nodes.keys():
            if node_idx >= 10000:
                continue
            host = self.nodes[node_idx]['host']
            db_folder = self.get_node_consistent_id(node_idx).replace('.', '_').replace('-', '_')
            if commands.get(host) is None:
                commands[host] = [
                    # 'cd %s; zip --symlinks -r ignite_lfs_%s.%s.zip %s' % (
                    'cd %s; tar -cf ignite_lfs_%s.%s.tar %s' % (
                        self.config['rt']['remote']['test_module_dir'],
                        tag,
                        host,
                        '*server*/work/db/%s/cache* *server*/work/db/%s/meta* *server*/work/binary_meta/* *server*/work/marshaller/*' % (db_folder, db_folder),
                    ),
                    'mv %s/ignite_lfs_%s.%s.tar %s' % (
                        self.config['rt']['remote']['test_module_dir'],
                        tag,
                        host,
                        dir_path
                    ),
                    'stat -c "%' + 's" %s/ignite_lfs_%s.%s.tar' % (
                        dir_path,
                        tag,
                        host
                    ),
                ]
        results = self.ssh.exec(commands, timeout=timeout)
        total_size = 0
        for host in results.keys():
            lines = results[host][2]
            m = search('^([0-9]+)\n', lines)
            if m:
                total_size += int(m.group(1))
        log_print("Ignite LFS stored in '%s' in %s sec, size: %s bytes" % (
            tag, int(time() - started), "{:,}".format(total_size))
                  )
        log_print()

    def restore_lfs(self, tag, dir_path=None):
        log_print("Restore Ignite LFS from '%s' ... " % tag)
        if dir_path is None:
            dir_path = self.config['remote']['suite_var_dir']
        commands = {}
        started = time()
        for node_idx in self.nodes.keys():
            if node_idx >= 50000:
                continue
            host = self.nodes[node_idx]['host']
            if commands.get(host) is None:
                commands[host] = [
                    'cp -f %s/ignite_lfs_%s.%s.tar %s' % (
                        dir_path,
                        tag,
                        host,
                        self.config['rt']['remote']['test_module_dir']
                    ),
                    'cd %s; tar -xf ignite_lfs_%s.%s.tar ' % (
                        self.config['rt']['remote']['test_module_dir'],
                        tag,
                        host,
                    )
                ]
        results = self.ssh.exec(commands)
        log_print("Ignite LFS restored from '%s' in %s sec" % (tag, int(time() - started)))
        log_print()

    def delete_lfs(self, node_id=None):
        log_print("Delete Ignite LFS for ignite %s ... " % self.name)
        commands = {}
        started = time()
        node_list = self.get_all_default_nodes() if node_id is None else range(int(node_id), int(node_id + 1))
        for node_idx in node_list:
            host = self.nodes[node_idx]['host']
            if commands.get(host) is None:
                commands[host] = []
            commands[host] += [
                'cd {test_module_dir}; '
                'rm -rf {ignite_name}.server.{node_idx}/work/db/* '
                '{ignite_name}.server.{node_idx}/work/binary_meta/* '
                '{ignite_name}.server.{node_idx}/work/marshaller/*'.format(
                    test_module_dir=self.config['rt']['remote']['test_module_dir'],
                    ignite_name=self.name,
                    node_idx=node_idx
                )
            ]
        log_print(commands, color='debug')
        results = self.ssh.exec(commands)
        log_print("Ignite LFS for ignite %s deleted in %s sec" % (self.name, int(time() - started)))
        log_print()

    def exists_stored_lfs(self, tag, dir_path=None):
        log_print("Looking up stored Ignite LFS tagged '%s' ... " % tag)
        if dir_path is None:
            dir_path = self.config['remote']['suite_var_dir']
        commands = {}
        started = time()
        for node_idx in self.nodes.keys():
            if node_idx >= 1000:
                continue
            host = self.nodes[node_idx]['host']
            if commands.get(host) is None:
                commands[host] = [
                    'ls %s | grep "ignite_lfs_%s.%s.tar" ' % (
                        dir_path,
                        tag,
                        host,
                    ),
                ]
        results = self.ssh.exec(commands)
        found = True
        for host in results.keys():
            if not 'ignite_lfs_%s' % tag in ''.join(results[host]):
                found = False
                break
        if found:
            log_print("Ignite LFS tagged '%s' found in %s sec" % (tag, int(time() - started)))
        else:
            log_print("Ignite LFS tagged '%s' not found in %s sec" % (tag, int(time() - started)))
        log_print()

        return found

    def remove_additional_nodes(self):
        additional_nodes = self.get_all_additional_nodes()
        for node_id in additional_nodes:
            if self.nodes[node_id]['status'] == NodeStatus.KILLED:
                del self.nodes[node_id]
            else:
                log_print(f'cannot remove running additional node {node_id}', color='red')

