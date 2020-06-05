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

from .appexception import AppException, MissedRequirementException
from .appconfigbuilder import AppConfigBuilder
from .nodestatus import NodeStatus
from ..util import log_print
from ..sshpool import SshPool


class App:
    config_builder = None
    nodes = {}
    config = None
    ssh = None
    name = ''
    app_type = ''
    artifact_name = ''

    def __init__(self, *args, **kwargs):
        # print('App.__init__')
        if len(args) == 1 and isinstance(args[0], self.__class__):
            self.__dict__ = args[0].__dict__
        else:
            name, config, ssh = args[0], args[1], args[2]
            self.config = config
            self.ssh: SshPool = ssh
            self.nodes = {}
            self.app_type = None
            self.name = name
            if 'name' in kwargs and kwargs['name']:
                self.name = kwargs['name']
            self.artifact_name = self.name
            if 'artifact_name' in kwargs and kwargs['artifact_name']:
                self.artifact_name = kwargs['artifact_name']

    @classmethod
    def create_config_builder(cls, ssh, config):
        cls.config_builder = AppConfigBuilder(ssh, config, cls)

    @classmethod
    def get_config_types(cls):
        """
        Override in children App to declare which template config files your application provides.
        :return: dictionary: {
            <config_type>: <config template file name>
        }
        """
        return dict()

    def check_requirements(self):
        """
        Override in children App to perform check of environment/artifact requirements before running app.
        :return: None, raise MissedRequirementException when requirements are not fulfilled.
        """
        pass

    def setup(self):
        pass

    def teardown(self):
        pass

    def require_artifact(self, artifact_type):
        artf_found = False
        for artf_name in self.config['artifacts'].keys():
            if self.config['artifacts'][artf_name].get('type') == artifact_type \
                    and self.config['artifacts'][artf_name].get('path'):
                artf_found = True
                break
        if not artf_found:
            raise MissedRequirementException(
                "No suitable artifact '%s' found for application '%s' " % (artifact_type, self.__class__.__name__))

    def require_environment(self, name):
        if self.config['environment'].get('apps_use_global_hosts', False):
            if name not in self.config['environment']:
                self.config['environment'][name] = {}
            for key in ['server_hosts', 'client_hosts']:
                self.config['environment'][name][key] = self.config['environment'].get(key, [])
            for key in ['clients_per_host', 'servers_per_host']:
                self.config['environment'][name][key] = self.config['environment'].get(key, 1)
        else:
            if not self.config['environment'].get(name):
                raise MissedRequirementException("No environment section found for '%s' application" % name)
            app_env = False
            if self.config['environment'][name].get('server_hosts') or \
                    self.config['environment'][name].get('client_hosts'):
                app_env = True
            if not app_env:
                raise MissedRequirementException('No environment section found for %s application' % name)

    def _mark_scripts_executable(self, artifact_type, glob_mask='bin/*.sh'):
        for artf in self.config['artifacts'].keys():
            if self.config['artifacts'][artf].get('type') and self.config['artifacts'][artf]['type'] == artifact_type:
                self.ssh.exec(
                    ["chmod -v 0755 %s/%s" % (self.config['artifacts'][artf]['remote_path'], glob_mask)]
                )

    def grep_log(self, *args, **kwargs):
        """
        Find node attributes in log files in two phase:
          1 phase: cat/grep log files on remote hosts and collect lines matched <remote_regex>
          2 phase: apply <local_regex> to found lines to extract the value of attribute
        It is possible to use one <regex> instead of local and remote regex
        :param args:    the list of node ids
        :param kwargs:  the dictionary of looking attributes in format
                        <attr_name>={regex: <regex>, remote_regex: <regex>, local_regex: <regex>, type: '<data type name>'}}
        :return:
        """
        # Check passed arguments
        if len(args) == 0:
            raise AppException("At least one node id must pass to method")
        if len(kwargs) == 0:
            raise AppException("At least one attribute must pass to method")
        ids = []
        if isinstance(args[0], int):
            ids = args
        else:
            raise AppException("Wrong arguments type: the list of integers is expected")
        for attr_name in kwargs.keys():
            if kwargs[attr_name].get('regex') is not None:
                kwargs[attr_name]['local_regex'] = kwargs[attr_name].get('regex')
                kwargs[attr_name]['remote_regex'] = kwargs[attr_name].get('regex')
            for attr_param in ['local_regex', 'remote_regex']:
                if kwargs[attr_name].get(attr_param) is None:
                    raise AppException("Missed %s for attribute %s " % (attr_param, attr_name))
        cmd = {}
        seek_attrs = sorted(kwargs.keys())
        # Construct the dictionary with remote commands
        attrs = {}
        for id in ids:
            attrs[id] = {}
            host = self.nodes[id]['host']
            for attr_name in seek_attrs:
                cat_tmpl = "echo {}; echo {}; cat {}".format(id, attr_name, self.nodes[id]['log'])
                if cmd.get(host) is None:
                    cmd[host] = []

                cmd[host].append("{cat} | grep {options} '{condition}'".format(
                    cat=cat_tmpl,
                    options=kwargs[attr_name].get('remote_grep_options', ''),
                    condition=kwargs[attr_name]['remote_regex'])
                )
        result = self.ssh.exec(cmd)
        # Process the results
        for host in result.keys():
            cmd_outputs = list(result[host])
            for cmd_output_idx in range(0, len(cmd_outputs)):
                # Split command output to lines
                lines = cmd_outputs[cmd_output_idx].split('\n')
                # First line is node id
                id = int(str(lines[0]).rstrip())
                # Second line is attribute name
                attr_name = str(lines[1]).rstrip()
                # Set None for attribute
                attrs[id][attr_name] = None
                starting_point = len("{}\n{}".format(id, attr_name))
                if kwargs[attr_name].get('ignore_multiline', False):
                    sarched_str = cmd_outputs[cmd_output_idx][starting_point:].replace('\n', '')
                else:
                    sarched_str = cmd_outputs[cmd_output_idx][starting_point:]
                m = search(
                    kwargs[attr_name]['local_regex'],
                    sarched_str
                )
                if m:
                    if kwargs[attr_name].get('get_all_found', False):
                        val = m.groups()
                    else:
                        val = m.group(1)
                    attr_type = kwargs[attr_name].get('force_type', kwargs[attr_name].get('type'))
                    # Set type
                    if attr_type == 'int':
                        val = int(val)
                    attrs[id][attr_name] = val
        return attrs

    def kill_nodes(self, *args):
        """
        Kill nodes by pid
        :param args:    the list of nodes ids
        :return:        None
        """
        ids = []
        if len(args) == 0:
            ids = list(self.nodes.keys())
        else:
            ids = args
        cmd = {}
        for id in ids:
            if self.nodes.get(id):
                host = self.nodes[id]['host']
                if self.nodes[id].get('PID'):
                    self.nodes[id]['status'] = NodeStatus.KILLING
                    log_print(f'Kill node {id} at host {host}')
                    if not cmd.get(host):
                        cmd[host] = []
                    cmd[host].append('nohup kill -9 %s > /dev/null 2>&1' % self.nodes[id]['PID'])
                else:
                    log_print(f'There is no PID for node {id}: already killed')
            else:
                log_print(f'No node {id} in the grid to kill')
        return self.ssh.exec(cmd)

    def set_node_option(self, node_filter, opt_name, opt_value):
        """
        Set option for node or node group
        :param node_filter: node index(es) or '*' for all nodes
        :param opt_name:    option name
        :param opt_value:   option value
        :return:
        """
        for node_idx in sorted(self.nodes.keys()):
            if node_filter == '*' or node_idx in node_filter:
                self.nodes[node_idx].update({opt_name: opt_value})

