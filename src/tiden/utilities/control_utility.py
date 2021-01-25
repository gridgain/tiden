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
from collections import OrderedDict
from os.path import basename
from re import search, sub
from time import sleep
from uuid import uuid4

from ..apps.ignite.igniteexception import IgniteException
from ..report.steps import step
from ..tidenexception import TidenException
from ..util import print_red, log_print, log_put, version_num
from ..logger import get_logger
from ..assertions import *
from .base_utility import BaseUtility


class ControlUtility(BaseUtility):

    def __init__(self, ignite, parent_cls=None):
        super().__init__(ignite, parent_cls=parent_cls)
        self.commands = None
        self.auth_login = None
        self.auth_password = None
        self.ssl_connection_enabled = False
        self.authentication_enabled = False
        self.ssl_conn_tuple = None
        self.ignite_version = None
        self.ignite_version_num = None

    def get_ssh(self):
        if hasattr(self.ignite, 'docker_ssh'):
            return self.ignite.docker_ssh
        return self.ignite.ssh

    ssh = property(get_ssh, None)

    def enable_authentication(self, login, password):
        self.authentication_enabled = True
        self.auth_login = login
        self.auth_password = password

    def enable_ssl_connection(self, conn_tuple):
        self.ssl_conn_tuple = conn_tuple
        self.ssl_connection_enabled = True

    def __return_ssl_connection_string(self):
        self.__update_commands()
        return '{} --{} {} --{} {} --{} {} --{} {}'.\
                                         format(
            self.ssl_keys.get('ssl_enabled', ''),
            self.ssl_keys['keystore'], self.ssl_conn_tuple.keystore_path,
            self.ssl_keys['keystore-password'], self.ssl_conn_tuple.keystore_pass,
            self.ssl_keys['truststore'], self.ssl_conn_tuple.truststore_path,
            self.ssl_keys['truststore-password'], self.ssl_conn_tuple.truststore_pass)

    def disable_authentication(self):
        self.authentication_enabled = False
        self.auth_login = None
        self.auth_password = None

    @step('Activate cluster')
    def activate(self, **kwargs):
        return self.__activate(True, **kwargs)

    @step('Deactivate cluster')
    def deactivate(self, **kwargs):
        return self.__activate(False, **kwargs)

    @step('CU command', attach_parameters=True)
    def control_utility(self, *args, **kwargs):
        self.latest_command = args = list(args)
        log_print(f"Control utility {' '.join(args)}")
        args = list(args)
        client_host = self.ignite.get_and_inc_client_host()
        server_host = None
        server_port = None
        bg = ''
        too_many_lines_num = 100

        alive_server_nodes = self.ignite.get_alive_default_nodes() + self.ignite.get_alive_additional_nodes()
        if 'node' in kwargs:
            alive_server_nodes = [kwargs['node']]

        elif 'use_same_host' in kwargs:
            alive_server_nodes = [node for node in alive_server_nodes if
                                  self.ignite.nodes[node].get('host') == client_host]

        elif 'use_another_host' in kwargs:
            alive_server_nodes = [node for node in alive_server_nodes if
                                  self.ignite.nodes[node].get('host') != client_host]
        if kwargs.get('reverse', False):
            alive_server_nodes = list(reversed(alive_server_nodes))
        for node_idx in alive_server_nodes:
            server_host = self.ignite.nodes[node_idx]['host']
            if 'binary_rest_port' not in self.ignite.nodes[node_idx]:
                # this node not run or killed, skip to next node
                continue
            server_port = self.ignite.nodes[node_idx]['binary_rest_port']
            break
        if server_host is None or server_port is None:
            raise TidenException('Not found running server nodes')

        nohup = ''

        # log any control utility command
        background = ''
        if kwargs.get('background'):
            background = '&'
        if isinstance(kwargs.get('log'), str):
            log_path = kwargs['log']
        elif isinstance(kwargs.get('log'), bool) and not kwargs['log']:
            log_path = None
        else:
            test_dir = self.ignite.config['rt']['remote']['test_dir']
            first_command = sub(r'\W+', '', args[0])
            file_name = None
            for i in range(1, 10000):
                file_name = f'control.{self.ignite.grid_name}.{first_command}.{i}.log'
                ls_out = self.ssh.exec_on_host(server_host, [f'ls {test_dir}'])[server_host]
                if [file for file in ls_out[0].split('\n') if file_name == file]:
                    file_name = None
                else:
                    break
            if file_name is None:
                file_name = f'control.{self.ignite.name}.{first_command}.{str(uuid4())[:6]}.log'
            log_path = f'{test_dir}/{file_name}'

        if log_path:
            bg = f'> {log_path} 2>&1 {background}'

        if self.authentication_enabled:
            if self.auth_login:
                args.append(f'--user {self.auth_login}')
            if self.auth_password:
                args.append(f'--password {self.auth_password}')

        if self.ssl_connection_enabled:
            args.append(self.__return_ssl_connection_string())

        commands = {
            client_host: [
                f"cd {self.ignite.client_ignite_home}; "
                f"{nohup} bin/control.sh --host {server_host} --port {server_port} {' '.join(args)} {bg}"
            ]
        }

        self.ignite.logger.debug(commands)
        ssh_options = kwargs.get('ssh_options', {})

        results = self.ssh.exec(commands, **ssh_options)

        if log_path is not None and not background:
            limit = ''
            if kwargs.get('output_limit'):
                limit = f' | tail -n {kwargs["output_limit"]}'
            lines = self.ssh.exec_on_host(client_host, [f'cat {log_path}{limit}'])[client_host][0]
        else:
            lines = results[client_host][0]

        if kwargs.get('show_output', True):
            self.__print_utility_output(lines)

        self.latest_utility_output = lines
        self.latest_utility_host = client_host
        if kwargs.get('all_required'):
            success = self.check_content_all_required(
                lines, kwargs.get('all_required'),
                maintain_order=kwargs.get('maintain_order', None),
                escape=kwargs.get('escape', None),
                match_once_or_more=kwargs.get('match_once_or_more', None),
            )

            if len(lines.split('\n')) > too_many_lines_num:
                lines_to_show = '\n'.join(lines.split('\n')[:too_many_lines_num]) + '\n*** TOO MANY LINES TO SHOW ***'
            else:
                lines_to_show = lines

            if not success and not kwargs.get('background'):
                raise TidenException(''.join(lines_to_show))
        if kwargs.get('strict'):
            if 'Error:' in self.latest_utility_output:
                raise TidenException('control.sh --baseline command end up with exceptions')
        return self

    def __find_commands(self):
        nodes = self.ignite.get_all_default_nodes()
        if not nodes:
            raise TidenException("Can't find nodes to ask for help")
        ignite_home = self.ignite.nodes[nodes[0]]['ignite_home']
        ignite_host = self.ignite.nodes[nodes[0]]['host']

        output = self.ssh.exec_on_host(ignite_host, ['cd {}; bin/control.sh --help'.format(ignite_home)])
        if output[ignite_host]:
            output = output[ignite_host][0].split("\n")
            self.ssl_keys = {}
            if 'ssl_key_store_path' in ''.join(output):
                self.ssl_keys['keystore'] = 'ssl_key_store_path'
                self.ssl_keys['keystore-password'] = 'ssl_key_store_password'
                self.ssl_keys['truststore'] = 'ssl_truststore_path'
                self.ssl_keys['truststore-password'] = 'ssl_truststore_password'
            else:
                self.ssl_keys['keystore'] = 'keystore'
                self.ssl_keys['keystore-password'] = 'keystore-password'
                self.ssl_keys['truststore'] = 'truststore'
                self.ssl_keys['truststore-password'] = 'truststore-password'
            if 'ssl_enabled' in ''.join(output):
                self.ssl_keys['ssl_enabled'] = '--ssl_enabled'

            return self.__parse_commands(self.__parse_help(output))
        raise TidenException("Can't get control.sh help")

    def __parse_commands(self, parsed_help):
        commands = {}
        known_patterns = {
            'deactivate': 'deactivate',
            'activate': 'activate',
            'change cluster state active param': 'set_state_active',
            'change cluster state inactive param': 'set_state_inactive',
            'change cluster state active_read_only param': 'set_state_active_read_only',
            'add nodes': 'baseline_add',
            'remove nodes': 'baseline_remove',
            'based on version': 'baseline_version',
            'set baseline autoadjustment': 'baseline_autoadjustment',
            'set baseline': 'baseline_set',
            'cluster baseline topology': 'baseline_print',
            'ist or kill transactions': 'tx',
            'about specific transaction': 'tx_info',
            'caches': 'view_caches',
            'view diagnostic': 'view_diagnostic',
            'change cluster tag': 'change_tag',
            'change cluster state': 'set_state',
            'print current cluster state': 'state',
            'kill compute task': 'kill_compute_task',
            'kill service': 'kill_service',
            'kill sql query': 'kill_sql_query',
            'kill continuous query': 'kill_continuous_query',
            'kill scan query': 'kill_scan_query',
            'kill transaction by xid': 'kill_tx',
            'print the current master key name': 'print_master_key',
            'change the master key': 'change_master_key',
            # TODO: DR help requires additional parsing
        }
        for help_string, help_data in parsed_help.items():
            found = False
            for pattern, command_name in known_patterns.items():
                if pattern in help_string:
                    commands[command_name] = help_data.copy()
                    found = True
                    break
            if not found:
                log_print('WARN: Unknown command in control.sh help: %s' % help_string, 2, color='debug')
        change_state = parsed_help.get('change cluster state')
        return commands

    def __parse_help(self, output):
        output = [sub("\s+", " ", line.replace("\n", "")).strip() for line in output if line != '']
        if len(output) == 0:
            return {}
        commands_start_pattern = 'This utility can do the following commands:'
        help_old_pattern = 'Example: --host {ip} --port {port} --{activate/deactivate}'
        version_pattern = 'Control utility [ver. '
        version_line = [idx for idx, line in enumerate(output) if version_pattern in line]
        if len(version_line) > 0:
            self.ignite_version = output[version_line[0]].split(version_pattern)[1].split('#')[0]
            self.ignite_version_num = version_num(self.ignite_version)
        start_commands = [idx for idx, line in enumerate(output) if commands_start_pattern in line]
        if len(start_commands) == 0:
            for line in output:
                if help_old_pattern in line:
                    return {
                        'activate': {'attr': '--activate', 'force': ''},
                        'deactivate': {'attr': '--deactivate', 'force': ''},
                    }
            raise TidenException("Can't decipher help of control.sh for ignite %s" % self.get_ignite_version())

        start_commands_idx = start_commands[0]
        commands = output[start_commands_idx + 1:]
        force_attr_check = lambda _force_attr: _force_attr.startswith("[") \
                                               and _force_attr.endswith("]") \
                                               and _force_attr[1:3] == '--' \
                                               and ' ' not in _force_attr and '|' not in _force_attr
        help = {}
        for idx, line in enumerate(commands):
            next_line = commands[idx + 1:idx + 2]
            if line.endswith(":") and next_line \
                    and ('control.sh' in next_line[0] or 'control.(sh|bat)' in next_line[0]):
                action_name = line[:line.index(":")].lower().strip()
                control_attrs = next_line[0].replace(']--', '] --').split(" ")
                attr = None
                force_attr = ''
                for idx, control_attr in enumerate(control_attrs):
                    if str(control_attr).startswith("--"):
                        attr = control_attr
                        if force_attr_check(control_attrs[-1]):
                            force_attr = control_attrs[-1].replace("[", "").replace("]", "")
                            break

                all_force_attrs = ''
                if action_name == 'change cluster state':
                    all_force_attrs = ' '.join([sub("[\[\]]", "", ca) for ca in control_attrs if search("^\[--\w+\]$", ca)])
                    force_attr = ''

                found_parameters = [ca.split('|') for ca in control_attrs if search('^([a-zA-Z_]+\|[a-zA-Z_]+){2,}$', ca) and not search('\[|\]', ca)]
                if found_parameters:
                    for parameter in found_parameters[0]:
                        help[f'{action_name} {parameter.lower()} param'] = {'attr': f'{attr} {parameter} {all_force_attrs}', 'force': force_attr}
                else:
                    help[action_name] = {'attr': attr, 'force': force_attr}
                if 'transaction' in action_name:
                    for idx, control_attr in enumerate(control_attrs):
                        control_attr = control_attr.lower().replace('[', '').replace(']', '').replace('|', ' ')
                        control_attr_name = control_attr.split(' ')[0]
                        if 'kill' in control_attr:
                            help[action_name]['kill'] = control_attr_name
                        elif 'xid' in control_attr:
                            if 'xid' not in help[action_name]:
                                help[action_name]['xid'] = control_attr_name
                        elif 'duration' in control_attr:
                            if 'min_duration' not in help[action_name]:
                                help[action_name]['min_duration'] = control_attr_name
                        elif 'size' in control_attr:
                            if 'min_size' not in help[action_name]:
                                help[action_name]['min_size'] = control_attr_name
                        elif 'label' in control_attr:
                            if 'label' not in help[action_name]:
                                help[action_name]['label'] = control_attr_name
                        elif 'nodes' in control_attr:
                            if 'nodes' not in help[action_name]:
                                help[action_name]['nodes'] = control_attr_name
                        elif 'limit' in control_attr:
                            if 'limit' not in help[action_name]:
                                help[action_name]['limit'] = control_attr_name
                        elif 'order' in control_attr:
                            if 'order' not in help[action_name]:
                                help[action_name]['order'] = control_attr_name
                        elif 'servers' in control_attr:
                            srv_cli_attrs = control_attr.replace(' ', '|').split('|')
                            for srv_cli_attr in srv_cli_attrs:
                                if 'servers' in srv_cli_attr:
                                    if 'servers' not in help[action_name]:
                                        help[action_name]['servers'] = srv_cli_attr
                                if 'clients' in srv_cli_attr:
                                    if 'clients' not in help[action_name]:
                                        help[action_name]['clients'] = srv_cli_attr

        return help

    def get_ignite_version(self):
        if self.ignite_version is None:
            from tiden.testconfig import test_config
            self.ignite_version = test_config.get_ignite_version(self.ignite.name)
            self.ignite_version_num = version_num(self.ignite_version)
        return self.ignite_version

    def __update_commands(self):
        if self.commands is None:
            self.commands = self.__find_commands()

    def __check_command_supported(self, command):
        self.__update_commands()
        if command not in self.commands:
            raise TidenException('Command %s not supported in control.sh for version %s ' % (
                command, self.get_ignite_version()
            ))

    def get_force_attr(self, command):
        self.__check_command_supported(command)
        return self.commands[command].get('force', '')

    # TODO reuse control_utility
    def __activate(self, cmd, **kwargs):
        self.__update_commands()
        if self.commands.get('set_state_active'):
            command_name = 'set_state_active' if cmd else 'set_state_inactive'
        else:
            command_name = 'activate' if cmd else 'deactivate'

        log_print(f"{command_name.capitalize()} grid")

        activate_commands = {}
        check_commands = {}
        server_nodes_num = 0

        force_attr = self.get_force_attr(command_name)
        command = self.commands[command_name]['attr']

        auth_attr = ''
        if self.authentication_enabled:
            if self.auth_login:
                auth_attr += f' --user {self.auth_login} '
            if self.auth_password:
                auth_attr += f' --password {self.auth_password} '

        if self.ssl_connection_enabled:
            auth_attr += self.__return_ssl_connection_string()

        nodes = self.ignite.get_alive_default_nodes() + self.ignite.get_alive_additional_nodes()
        assert len(nodes) > 0, "FATAL: no server nodes, nothing to activate"

        if kwargs.get('activate_on_particular_node'):
            nodes = [kwargs.get('activate_on_particular_node')]

        for node_idx in nodes:
            if 'binary_rest_port' not in self.ignite.nodes[node_idx]:
                if kwargs.get('activate_on_particular_node'):
                    raise TidenException("Trying to activate/deactivate offline node")

                print_red(f"Unable to find port for {node_idx} node. Skipping.")
                continue

            host = self.ignite.nodes[node_idx]['host']
            bin_rest_port = self.ignite.nodes[node_idx]['binary_rest_port']
            ignite_home = self.ignite.nodes[node_idx]['ignite_home']
            activate_log = self.ignite.nodes[node_idx]['log'].replace('.log', f'.{command_name}.log')
            if kwargs.get('log'):
                activate_log = kwargs['log']
            if activate_commands.get(host) is None:
                activate_commands[host] = []
                check_commands[host] = []
            activate_commands[host].append(
                f"cd {ignite_home}; bin/control.sh --host {host} --port {bin_rest_port} "
                f"{auth_attr} {command} {force_attr} > {activate_log} 2>&1"
            )
            if cmd:
                check_commands[host].append(
                    f'cat {self.ignite.nodes[node_idx]["log"]} | '
                    f'grep "\('
                    f'Success final activate\|'
                    f'Successfully performed final activation steps\|'
                    f'Successfully activated caches\
                    )"'
                )
            else:
                check_commands[host].append(
                    'cat %s | grep "\('
                    'Success final deactivate\|'
                    'Successfully deactivated caches\|'
                    'Successfully deactivated datastructures, services and caches'
                    '\)"'
                    % self.ignite.nodes[node_idx]['log']
                )
            server_nodes_num += 1
        log_print(activate_commands, color='debug')
        self.ssh.exec(activate_commands, **kwargs)
        activated_server_nodes_num = 0
        timeout_counter = 0
        log_put("Waiting %sd nodes: 0/%s" % (command, server_nodes_num))
        completed = False
        activation_timeout = self.ignite.activation_timeout
        if 'activation_timeout' in kwargs:
            activation_timeout = int(kwargs['activation_timeout'])
        while timeout_counter < activation_timeout and not completed:
            results = self.ignite.ssh.exec(check_commands, **kwargs)
            activated_server_nodes_num = 0
            for host in results.keys():
                for out_lines in results[host]:
                    if len(out_lines) > 22:
                        activated_server_nodes_num += 1
            log_put(
                "Waiting %sd nodes: %s/%s, timeout %s/%s sec" % (
                    command,
                    activated_server_nodes_num,
                    server_nodes_num,
                    timeout_counter,
                    activation_timeout
                )
            )
            if cmd:
                if activated_server_nodes_num == server_nodes_num:
                    completed = True
            else:
                if activated_server_nodes_num == 0:
                    completed = True
            sleep(5)
            timeout_counter += 5
        log_print('')
        if cmd:
            if activated_server_nodes_num < server_nodes_num:
                raise IgniteException('Activation failed')
        else:
            if activated_server_nodes_num > 0:
                raise IgniteException('Deactivation failed')
        return True

    def _get_nodes_state_from_output(self):
        nodes = {}
        for line in self.latest_utility_output.split('\n'):
            found_in_baseline = search('ConsistentId=(.+),.+State=(.+),', line)
            if found_in_baseline:
                nodes[found_in_baseline.group(1)] = found_in_baseline.group(2)
            else:
                found_out_baseline = search('ConsistentId=(.+),', line)
                if found_out_baseline:
                    nodes[found_out_baseline.group(1)] = ''
        return nodes

    def set_baseline(self, topology_version, **kwargs):
        args = [
            '--baseline',
            f'version {topology_version}',
        ]

        force_attr = self.get_force_attr('baseline_version')
        if force_attr != '':
            args.append(force_attr)

        self.control_utility(*args, **kwargs)

        return self._get_nodes_state_from_output()

    @step('Set current topology as baseline')
    def set_current_topology_as_baseline(self, **kwargs):
        curr_top_version = self.get_current_topology_version()

        if not curr_top_version:
            message = 'ERROR: Could not find current topology version!!!'
            if kwargs.get('strict'):
                raise TidenException(message)
            else:
                log_print(message, color='red')
                return

        return self.set_baseline(curr_top_version, **kwargs)

    def get_current_topology_version(self, **kwargs):
        curr_top_version = None
        self.control_utility('--baseline', **kwargs)
        for line in self.latest_utility_output.split('\n'):
            m = search('Current topology version: (\d+)', line)
            if m:
                curr_top_version = m.group(1)
        return curr_top_version

    def get_current_baseline(self):
        self.control_utility('--baseline')
        return self._get_nodes_state_from_output()

    def idle_verify_dump(self, skip_zeros=False, cache_filter=False, exclude_caches=False,
                         copy_dir=None, key_dump=True, **kwargs):
        """
        Dump current caches metrics in file

        :param skip_zeros:  use option --skipZeros
        :param copy_dir:    directory to backup dump file (recommend to use test_dir)
        :return:            parsed caches dump
        """
        args = ["--cache", 'idle_verify']
        if key_dump:
            args.append('--dump')
        # args += ['--skipZeros'] if skip_zeros else []
        args += ['--skip-zeros'] if skip_zeros else []
        args += cache_filter.split() if cache_filter else []
        if (self.ignite_version_num >= 2070000 and self.ignite_version_num < 2070300) or \
                (self.ignite_version_num == 2080100):
            args += ['--excludeCaches', '{}'.format(exclude_caches)] if exclude_caches else []
        else:
            args += ['--exclude-caches', '{}'.format(exclude_caches)] if exclude_caches else []
        print(args)
        self.control_utility(*args, **kwargs)
        if key_dump:
            return self.get_parsed_dump_items(copy_path=copy_dir)

    def get_idle_verify_dump_path(self):
        """
        Find dump file path in control.sh logs
        """
        for line in self.latest_utility_output.split("\n"):
            if line.startswith('VisorIdleVerifyDumpTask successfully written output'):
                path = line[line.index("'") + 1:line.rindex("'")]
                log_print('Found dump file: {}'.format(basename(path)))
                return path
        raise IgniteException("Can't find idle verify dump path")

    def get_parsed_dump_items(self, file_path=None, copy_path=None):
        """
        Searching for partition description in dump file

        :param file_path:   dump file path
        :param copy_path:   path to copy dump file
        :return:            list({
                                "info": {
                                            "grpName": str,
                                            "grpId": str,
                                            "partId": str
                                        },
                                "instances": {
                                            "isPrimary": str,
                                            "consistentId": str,
                                            "updateCntr": str,
                                            "size": str,
                                            "partHash": str
                                        }
                            })
        """
        if file_path is None:
            file_path = self.get_idle_verify_dump_path()

        # searching on all hosts because dump file stored in first server node directory
        if copy_path:
            cmd = 'cp {src} {dst} && cat {src}'.format(src=file_path, dst=copy_path)
        else:
            cmd = 'cat {}'.format(file_path)
        print_red('Idle verify dump: %s' % cmd)
        result = self.ssh.exec([cmd])
        for host, command_out in result.items():
            command_out = command_out[0]
            if 'No such file or directory' not in command_out and command_out != '':
                result = command_out

        # filter body
        lines = result.split("\n")
        body_lines = []
        for line in lines:
            read = line.startswith("Partition")
            if read:
                body_lines.append(line)

        result_list = []
        structure = {}
        for line in body_lines:
            if line.startswith("Partition:"):

                structure["info"] = {"name": line[line.index(":") + 1:line.index("[")]}

                for pair in line[line.index("[") + 1:line.index("]")].split(","):
                    key, value = pair.strip().split("=")
                    structure["info"][key] = value

            elif line.startswith("Partition instances:"):

                structure["instances"] = []

                items_line = line[line.index("[") + 1:line.rindex("]")]
                for partition in items_line.split("],"):

                    instance = {"name": partition[:partition.index("[")].strip()}

                    for pair in partition[partition.index("[") + 1:].split(","):
                        pair = pair.replace("]", "").strip()
                        key, value = pair.split("=")
                        instance[key] = value

                    structure["instances"].append(instance)

            # two lines for two dict keys
            if len(structure) == 2:
                result_list.append(structure)
                structure = {}

        return result_list

    def check_all_msgs_in_utility_output(self, lines_to_search):
        utility_output = self.latest_utility_output.split('\n')
        for line in lines_to_search:
            found = [item for item in utility_output if line in item]
            tiden_assert_equal(1, len(found),
                               'Str %s found in utility output: %s' % (line, '\n'.join(utility_output))
                               )

    def get_any_server_node_host_port(self):
        """
        Returns server host and command port from first alive default node.
        :return:
        """
        server_host, server_port = None, None
        alive_server_nodes = self.ignite.get_alive_default_nodes()

        for node_idx in alive_server_nodes:
            server_host = self.ignite.nodes[node_idx]['host']
            if 'binary_rest_port' not in self.ignite.nodes[node_idx]:
                # this node not run or killed, skip to next node
                continue
            server_port = self.ignite.nodes[node_idx]['binary_rest_port']
            break
        if server_host is None or server_port is None:
            raise TidenException('Not found running server nodes')
        return server_host, server_port

    def get_next_run_count(self):
        self.run_count += 1
        return self.run_count

    @step('Remove {consistent_id} node from baseline')
    def remove_node_from_baseline(self, consistent_id, **kwargs):
        args = [
            '--baseline',
            'remove',
            consistent_id,
        ]

        force_attr = self.get_force_attr('baseline_remove')
        if force_attr != '':
            args.append(force_attr)

        self.control_utility(*args, background=kwargs.get('background'), log=kwargs.get('log'))
        sleep(5)  # TODO: make sure automated snapshot created

    def add_node_to_baseline(self, consistent_id, **kwargs):
        args = [
            '--baseline',
            'add',
            consistent_id,
        ]

        force_attr = self.get_force_attr('baseline_add')
        if force_attr != '':
            args.append(force_attr)

        self.control_utility(*args, background=kwargs.get('background'), log=kwargs.get('log'))
        sleep(5)  # TODO: make sure automated snapshot created

    def get_kill_subcommand(self):
        return self.get_command('tx', 'kill')

    def get_command(self, command, subcommand):
        self.__check_command_supported(command)
        command_attrs = self.commands[command]
        return command_attrs[subcommand]

    def kill_transactions(self, force=True, **kwargs):
        """
        Kill transactions, either all or by given filter
        :param force:
        :param kwargs:
            xid
            min_duration
            min_size
            label
            nodes
            order
            limit
            servers
            clients
        :return:
        """
        self.__check_command_supported('tx')
        tx_command_attrs = self.commands['tx']

        cmd = [
            '--tx',
            tx_command_attrs['kill']
        ]
        for attr, value in kwargs.items():
            if attr not in tx_command_attrs.keys():
                raise TidenException('--tx command %s attribute unknown in version %s' % (
                    attr, self.get_ignite_version()))
            if attr in ['servers', 'clients']:
                cmd.append(tx_command_attrs[attr])
            else:
                cmd.extend([tx_command_attrs[attr], str(value)])
        if force:
            cmd.append(self.get_force_attr('tx'))
        self.control_utility(' '.join(cmd))

    def list_transactions(self, **kwargs):
        """
        List transactions, either all or by given filter
        :param kwargs:
        Following arguments are handled as filters, all other are passed to .control_utility as is.
            xid
            min_duration
            min_size
            label
            nodes
            order
            limit
            servers
            clients
        :return:
        """
        self.__check_command_supported('tx')
        tx_command_attrs = self.commands['tx']

        cmd = [
            '--tx',
        ]
        for attr, value in kwargs.items():
            if attr not in tx_command_attrs.keys():
                raise TidenException("--tx command '%s' attribute unknown in version %s" % (
                    attr, self.get_ignite_version()))
            if attr in ['servers', 'clients']:
                cmd.append(tx_command_attrs[attr])
            else:
                cmd.extend([tx_command_attrs[attr], str(value)])
        self.control_utility(' '.join(cmd))

    def is_baseline_autoajustment_supported(self):
        try:
            self.__check_command_supported('baseline_autoadjustment')
            return True
        except TidenException:
            return False

    def disable_baseline_autoajustment(self):
        self._disable_enable_autoajustment()

    def enable_baseline_autoajustment(self):
        self._disable_enable_autoajustment(disable=False)

    def _disable_enable_autoajustment(self, disable=True):
        if self.is_baseline_autoajustment_supported():
            args = [
                '--baseline',
                'auto_adjust {}'.format('disable' if disable else 'enable'),
            ]

            force_attr = self.get_force_attr('baseline_autoadjustment')
            if force_attr != '':
                args.append(force_attr)

            self.control_utility(*args)
            sleep(5)
        else:
            log_print('ERROR: Could not disable baseline auto-adjustment as it is not supported'.
                      format('disable' if disable else 'enable'), color='red')

    def get_auto_baseline_params(self):
        """
        Returns status and soft timeout for baseline auto adjustment from previous commnd's
        output
        :return: tuple of status and soft timeout
        """
        status, soft_timeout = None, None
        if self.latest_utility_output:
            m = search('Baseline auto adjustment ([\w]+):', self.latest_utility_output)
            if m:
                status = m.group(1)
            m = search('softTimeout=(\d+)', self.latest_utility_output)
            if m:
                soft_timeout = int(m.group(1))
        return status, soft_timeout

    def __print_utility_output(self, output):
        for line in output.split('\n'):
            log_print(line)

