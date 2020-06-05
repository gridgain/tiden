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

from re import search
from sys import stdout
from time import time, sleep

from ...nodestatus import NodeStatus
from ... import AppException
from .ignitenodesmixin import IgniteNodesMixin
from ....util import log_put, log_print, get_logger
from ....tidenexception import TidenException
from ....report.steps import step


class IgniteTopologyMixin(IgniteNodesMixin):
    """
    Incapsulates processing of 'Topology snapshot [ver=...]' messages.
    """

    snapshot_timeout = 120

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.known_fatal_errors = {
            'jvm options error':
                {'regex': '(^Error: Could not create the Java Virtual Machine\.)',
                 'remote_grep_options': '-E'},
            'jvm crash':
                {'regex': '(^\# A fatal error has been detected by the Java Runtime Environment:.*)',
                 'remote_grep_options': '-E'},
            'Spring config error':
                {'regex': '(Failed to instantiate Spring XML application context)',
                 'remote_grep_options': '-E'},
            'SPI Exception':
                {'regex': '(IgniteSpiException: SPI parameter failed condition check: .+)',
                 'remote_grep_options': '-E'},
            'Failure handler':
                {'regex': '(.+JVM will be halted immediately due to the failure: .+)',
                 'remote_grep_options': '-E'},
            'Error on node start':
                {'regex': '(^.+Exception during start processors, node will be stopped and close connections)',
                 'remote_grep_options': '-E'},
            'Error joining to topology':
                {'regex': '(^.+Failed to read magic header)',
                 'remote_grep_options': '-E'}
        }

    def set_snapshot_timeout(self, timeout):
        self.snapshot_timeout = timeout

    def get_snapshot_timeout(self):
        return self.snapshot_timeout

    def last_topology_snapshot(self, snapshot_text='', check_only_servers=False, exclude_nodes=[]):
        """
        Get latest topology snapshot from all server nodes
        :param snapshot_text: additional test to filter local and remote updates
        :param check_only_servers: check only servers nodes logs
        :param exclude_nodes: exclude server's node log from topology check (for example if node fails).
        :return: the list of dictionaries with following keys:
        ver, servers, clients, heap, CPUs and node
        """
        commands = {}
        nodes_to_check = self.get_all_default_nodes() + self.get_all_additional_nodes() + self.get_all_client_nodes()
        if check_only_servers:
            nodes_to_check = self.get_all_default_nodes() + self.get_all_additional_nodes()

        if exclude_nodes:
            nodes_to_check = [node_id for node_id in nodes_to_check if node_id not in exclude_nodes]

        for node_idx in nodes_to_check:
            if self.nodes[node_idx].get('status', NodeStatus.DISABLED) in (NodeStatus.STARTED, NodeStatus.STARTING):
                host = self.nodes[node_idx]['host']

                if host not in commands:
                    commands[host] = []

                if self.nodes[node_idx].get('log') is not None:
                    commands[host].append(
                        'cat %s | grep -E "%s.+Topology snapshot" | tail -n 1000' % (
                            self.nodes[node_idx]['log'],
                            snapshot_text
                        )
                    )

        results = self.ssh.exec(commands)

        output = []
        if len(results) > 0:
            for host in results.keys():
                for host_results in results[host]:
                    host_snapshots = {}
                    for node_data in host_results.split('\n'):
                        match = search(
                            '\[(ver)=(\d+),.*(servers)=(\d+), (clients)=(\d+),.*(CPUs)=(\d+),.* (heap)=([0-9\.MBG]+).*\]',
                            node_data
                        )
                        if match:
                            snapshot = {}
                            for idx in range(1, 6):
                                if match.group(2 * idx - 1) != 'heap':
                                    snapshot[match.group(2 * idx - 1)] = int(match.group(2 * idx))
                                else:
                                    snapshot[match.group(2 * idx - 1)] = match.group(2 * idx)
                            host_snapshots[snapshot['ver']] = snapshot.copy()
                    if host_snapshots:
                        # Store only snapshot with the maximum version number
                        output.append(host_snapshots[max(host_snapshots.keys())])
        return output

    def get_current_topology_version(self, snapshot_text=''):
        last_topology_version = 0

        current_snapshots = self.last_topology_snapshot(snapshot_text)
        for current_snapshot in current_snapshots:
            if last_topology_version < int(current_snapshot['ver']):
                last_topology_version = int(current_snapshot['ver'])

        return last_topology_version

    @step()
    def wait_for_topology_snapshot(self, server_num=None, client_num=None, comment='', **kwargs):
        """
        Wait for topology snapshot
        :param server_num:  the servers number that expected in topology snapshot
        :param client_num:  the servers number that expected in topology snapshot
        :param comment:     the additional text printed out during waiting process
        :return: none
        """

        wait_for = {
            'servers': server_num,
            'clients': client_num,
        }

        snapshot_found = False
        started = int(time())
        timeout_counter = 0
        other_nodes = kwargs.get('other_nodes', 0)
        max_topology_nodes = (server_num if server_num else 0) + (client_num if client_num else 0) - other_nodes

        snapshot_text = kwargs.get('snapshot_text', '')
        snapshot_timeout = kwargs.get('timeout', self.snapshot_timeout)
        first_snapshot = {
            'servers': '?',
            'clients': '?'
        }
        while timeout_counter < snapshot_timeout:
            log_put(
                "Waiting for topology snapshot: server(s) %s/%s, client(s) %s/%s, timeout %s/%s sec %s " %
                (
                    first_snapshot['servers'],
                    '*' if server_num is None else server_num,
                    first_snapshot['clients'],
                    '*' if client_num is None else client_num,
                    timeout_counter,
                    snapshot_timeout,
                    comment
                )
            )
            stdout.flush()

            snapshots = self.last_topology_snapshot(snapshot_text,
                                                    check_only_servers=kwargs.get('check_only_servers', False),
                                                    exclude_nodes=kwargs.get('exclude_nodes_from_check', []))
            errors = self.check_fatal_errors_in_logs()
            if errors:
                raise AppException('Found errors on start nodes:\n' + errors)
            # print(snapshots)
            get_logger('tiden').debug(snapshots)
            # Wait for at least one Topology snapshot
            skip_nodes_check = 'skip_nodes_check' in kwargs or 'exclude_nodes_from_check' in kwargs
            if not snapshots or (len(snapshots) < max_topology_nodes and not skip_nodes_check):
                sleep(2)
                timeout_counter = int(time()) - started
                continue

            # Wait for all nodes to have the same topology version
            # Otherwise large topology under ZooKeeper may fail
            first_snapshot = snapshots.pop()
            if not all(first_snapshot['ver'] == snapshot['ver'] for snapshot in snapshots):
                sleep(2)
                timeout_counter = int(time()) - started
                continue

            snapshot_found = True

            # Wait for expected number of servers/clients
            for node_type in wait_for.keys():
                if wait_for[node_type] is None:
                    continue
                snapshot_found = snapshot_found and (wait_for[node_type] == first_snapshot[node_type])

            if snapshot_found:
                break

            sleep(2)
            timeout_counter = int(time()) - started
        log_put(
            "Waiting for topology snapshot: server(s) %s/%s, client(s) %s/%s, timeout %s/%s sec %s " %
            (
                first_snapshot['servers'],
                '*' if server_num is None else server_num,
                first_snapshot['clients'],
                '*' if client_num is None else client_num,
                timeout_counter,
                snapshot_timeout,
                comment
            )
        )
        stdout.flush()
        log_print('')
        if not snapshot_found:
            msg = "Error: no suitable topology snapshot found for servers=%s and clients=%s" \
                  % (server_num, client_num)
            raise TidenException(msg)

    def check_fatal_errors_in_logs(self):
        node_ids = []
        for node_id in self.nodes.keys():
            if self.nodes[node_id]:
                if self.nodes[node_id]['status'] == NodeStatus.STARTING and self.nodes[node_id].get('log'):
                    node_ids.append(node_id)
                elif self.nodes[node_id]['status'] == NodeStatus.STARTING and not self.nodes[node_id].get('log'):
                    log_print('Found node STARTING status and no log file:\n{}'.format(self.nodes[node_id]),
                              color='red')
        if len(node_ids) == 0:
            return
        known_fatal_errors_from_log = self.grep_log(*node_ids, **self.known_fatal_errors)
        message = ''
        for node_id_errors in known_fatal_errors_from_log:
            for error in known_fatal_errors_from_log[node_id_errors].items():
                if error[1]:
                    message += f'Error in logs of node {node_id_errors}. {error[0]}: {error[1]}\n'
        return message

