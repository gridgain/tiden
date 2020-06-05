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

from ..tidenexception import TidenException
from ..util import *
from shutil import copyfile
from os import mkdir

from ..xmlconfigbuilder import IgniteTestContext


class GeneralTestCase:
    current_context = 'default'

    def __init__(self, config, ssh):
        self.config = config
        self.ssh = ssh
        self.data = {}

        # configuration file variables
        self.contexts = {'default': IgniteTestContext(self.config)}

        if config.get('rt'):
            self.config['rt']['resource_dir'] = self.get_source_resource_dir()
            # Copy resources in test resource directory
            test_resource_dir = self.get_resource_dir()
            if not path.exists(test_resource_dir):
                mkdir(test_resource_dir)

                res_dirs = [self.config['rt']['resource_dir']]
                if isinstance(self.config['rt']['resource_dir'], list):
                    res_dirs = self.config['rt']['resource_dir']

                for res_dir in res_dirs:
                    for file in glob("%s/*" % res_dir):
                        if path.isfile(file):
                            copyfile(file, "%s/%s" % (test_resource_dir, path.basename(file)))

            self.config['rt']['test_resource_dir'] = unix_path(test_resource_dir)
            write_yaml_file(config['config_path'], config)

    def get_resource_dir(self):
        """
        return path to var resources directory. defaults to <suite_var_dir>/<test_module>/res
        :return:
        """
        return "%s/res" % self.config['rt']['test_module_dir']

    def get_source_resource_dir(self):
        """
        return path to source suite resources directory. defaults to suites/<suite>/res/<module>
        :return:
        """
        resources_dirs = [
            "%s/res/common" % (self.config['suite_dir']),
            "%s/res/%s" % (self.config['suite_dir'], self.config['rt']['test_module'].split('.')[1][5:])
        ]

        return [res_dir for res_dir in resources_dirs if path.isdir(res_dir)]

    def setup(self):
        self.deploy()
        self.set_current_context('default')
        self.fix_shell_scripts_permissions()

    def fix_shell_scripts_permissions(self):
        # Fix shell scripts permissions
        for artf in self.config.get('artifacts', {}).keys():
            if self.config['artifacts'][artf].get('type') and self.config['artifacts'][artf]['type'] == 'ignite':
                self.ssh.exec(
                    ["chmod -v 0755 %s/bin/*.sh" % self.config['artifacts'][artf]['remote_path']]
                )

    def teardown(self):
        pass

    def deploy(self):
        # Upload resources
        files = []
        for file in glob("%s/*" % self.config['rt']['test_resource_dir']):
            if path.isfile(file):
                files.append(unix_path(file))
        self.ssh.upload(files, self.config['rt']['remote']['test_module_dir'])

    def get_suite_dir(self):
        return self.config['suite_dir']

    def create_test_context(self, name):
        self.contexts[name] = IgniteTestContext(self.config)

        return self.contexts[name]

    def get_contexts(self):
        return self.contexts.keys()

    def set_current_context(self, context_name):
        if context_name not in self.contexts:
            raise TidenException('Unknown context name! Currently created contexts: %s' % str(self.contexts.keys()))

        self.current_context = context_name

    def get_context_variable(self, variable_name, context=None):
        if not context:
            context = self.current_context

        if variable_name not in self.contexts[context].variables:
            return None

        return self.contexts[context].variables[variable_name]

    def get_client_config(self, context=None):
        if not context:
            context = self.current_context

        return self.contexts[context].client_result_config

    def get_server_config(self, context=None):
        if not context:
            context = self.current_context

        return self.contexts[context].server_result_config

    def get_current_context(self):
        return self.current_context

