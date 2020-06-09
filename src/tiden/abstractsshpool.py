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

from itertools import chain
from random import choice
from .util import log_print

debug_abstract_pool = False


class AbstractSshPool:
    def __init__(self, ssh_config=None, **kwargs):
        self.config = ssh_config if ssh_config is not None else {}
        self.hosts = self.config.get('hosts', [])

    def get_random_host(self):
        return choice(self.hosts)

    def trace_info(self):
        raise NotImplementedError

    def available_space(self):
        raise NotImplementedError

    def connect(self):
        raise NotImplementedError

    def download(self, remote_path, local_path, prepend_host=True):
        raise NotImplementedError

    def exec(self, commands, **kwargs):
        raise NotImplementedError

    def exec_on_host(self, host, commands, **kwargs):
        raise NotImplementedError

    def jps(self, jps_args=None, hosts=None, skip_reserved_java_processes=True):
        raise NotImplementedError

    def dirsize(self, dir_path, *args):
        raise NotImplementedError

    def upload(self, files, remote_path):
        raise NotImplementedError

    def not_uploaded(self, files, remote_path):
        raise NotImplementedError

    def killall(self, name, sig=-9, skip_reserved_java_processes=True, hosts=None):
        raise NotImplementedError

    def exec_at_nodes(self, nodes, func: lambda node_id, node: str):
        """
        Execute per-node command at hosts
        :param nodes: dictionary node_idx -> node
        :param func: per-node command generation function
        :return: dictionary node_idx -> output of command
        """
        nodes_hosts = list(set([node['host'] for node in nodes.values()]))
        host_nodes = {
            host: [node_idx for node_idx, node in nodes.items() if node['host'] == host]
            for host in nodes_hosts
        }
        commands = {
            host: [func(node_idx, nodes[node_idx]) for node_idx in host_nodes[host]]
            for host in nodes_hosts
        }
        output = self.exec(commands)
        node_output = {node_idx: host_nodes[node['host']].index(node_idx) for node_idx, node in nodes.items()}
        result = {node_idx: output[node['host']][node_output[node_idx]] for node_idx, node in nodes.items()}
        return result

    def download_from_nodes(self, nodes, files, local_path, prepend_host=True):
        if debug_abstract_pool:
            log_print('download_from_nodes: \nnodes: ' +
                      repr(nodes) + '\nfiles: ' + repr(files) + '\nlocal_path: ' + local_path)
        nodes_hosts = list(set([node['host'] for node in nodes.values()]))
        host_nodes = {
            host: [node_idx for node_idx, node in nodes.items() if node['host'] == host]
            for host in nodes_hosts
        }
        remote_paths = {
            host: list(chain(*[[nodes[node_idx]['run_dir'] + '/' + file for file in files[node_idx]]
                               for node_idx in host_nodes[host] if node_idx in files]))
            for host in nodes_hosts
        }
        if debug_abstract_pool:
            log_print('download_from_nodes: \nnodes_hosts: ' +
                      repr(nodes_hosts) + '\nhost_nodes: ' + repr(host_nodes) + '\nremote_paths: ' + repr(remote_paths))
        return self.download(remote_paths, local_path, prepend_host=prepend_host)

    def ls(self, hosts=None, dir_path=None, params=None):
        ls_cmd = 'ls' if not params else 'ls {}'.format(params)
        ls_command = ['{}'.format(ls_cmd)] if not dir_path else ['{} {}'.format(ls_cmd, dir_path)]

        if hosts:
            ls_command = {host: ls_command for host in hosts}

        raw_results = self.exec(ls_command)
        results = {}
        for host in raw_results.keys():
            results[host] = (raw_results[host][0] if len(raw_results[host]) > 0 else '').rstrip().splitlines()

        return results
