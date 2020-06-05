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

from .ignitemixin import IgniteMixin
from ....util import log_print


class IgniteLibsMixin(IgniteMixin):
    """
    Provides classpath generation for Ignite start methods
    """
    # NB: this strictly corresponds to REPACK settings for `ignite` artifact,
    # may be better move it to config and let it be tweaked with test options
    DEFAULT_MODULES = [
        'ignite-spring',
        'ignite-zookeeper',
        'ignite-indexing',
        'ignite-log4j2',
        'gridgain-ultimate',
    ]

    modules = []

    def __init__(self, *args, **kwargs):
        # print('IgniteLibsMixin.__init__')
        super().__init__(*args, **kwargs)

        self.modules = set(IgniteLibsMixin.DEFAULT_MODULES)

    def activate_module(self, module_name):
        self.modules.add(module_name)

    def deactivate_module(self, module_name):
        self.modules.remove(module_name)

    def get_libs(self):
        libs = ['libs']
        libs.extend(['libs/' + module for module in self.modules])
        return libs

    def add_artifact_lib(self, artifact_name):
        assert artifact_name in self.config['artifacts'], \
            'Error artifact_name, couldn\'t find a match in %s' % self.config['artifacts']
        commands = {}
        for host_group in ['server_hosts', 'client_hosts']:
            for host in self.config['environment'][host_group]:
                commands[host] = []
                for node_index in self.nodes.keys():
                    if host == self.nodes[node_index]['host']:
                        commands[host] = [
                            'ln -s %s %s/libs/%s' % (
                                self.config['artifacts']['%s' % artifact_name]['remote_path'],
                                self.config['artifacts'][self.name]['remote_path'],
                                self.config['artifacts']['%s' % artifact_name]['remote_path'].split('/')[-1])
                        ]
        results = self.ssh.exec(commands)
        log_print('{} add to ignite'.format(artifact_name))

    def uninstall_module(self, module_name):
        """
        Removes module from artifact unconditionally
        :param module:
        :return:
        """
        for artifact_name in self.config['artifacts'].keys():
            if self.config['artifacts'][artifact_name].get('type') == self.app_type:
                results = self.ssh.exec(["rm -rf %s" % "%s/libs/%s" % (
                    self.config['artifacts']['%s' % artifact_name]['remote_path'], module_name
                )])

