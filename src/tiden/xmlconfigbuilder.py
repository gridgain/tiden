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

from jinja2 import Environment, FileSystemLoader

from .util import get_host_list


class IgniteTestContext:
    client_template_config = "client.xml"
    server_template_config = "server.xml"

    client_result_config = "client.xml"
    server_result_config = "server.xml"

    def __init__(self, config, **variables):
        self.config = config

        self.configs = {}

        self.variables = variables

        self.add_context_variables(
            addresses=get_host_list(
                self.config['environment'].get('server_hosts'),
                self.config['environment'].get('client_hosts')
            ),
        )

    def add_config(self, template, result):
        self.configs[template] = result

    def set_client_template_config(self, file_name):
        if self.client_template_config in self.configs.keys():
            del self.config[self.client_template_config]
        self.client_template_config = file_name
        self.configs[self.client_template_config] = self.client_result_config

    def set_server_template_config(self, file_name):
        if self.server_template_config in self.configs.keys():
            del self.config[self.server_template_config]
        self.server_template_config = file_name
        self.configs[self.server_template_config] = self.server_result_config

    def set_client_result_config(self, file_name):
        self.client_result_config = file_name
        self.configs[self.client_template_config] = self.client_result_config

    def set_server_result_config(self, file_name):
        self.server_result_config = file_name
        self.configs[self.server_template_config] = self.server_result_config

    def add_context_variables(self, **values):
        self.variables = {**self.variables, **values}

    def get_context_variables(self):
        return self.variables

    def build_config(self):
        XMLConfigBuilder(self.config['rt']['test_resource_dir'], self.configs, **self.variables).build()

    def build_and_deploy(self, ssh):
        from glob import glob
        from os import path
        from tiden.util import unix_path

        self.build_config()
        files = []
        for file in glob("%s/*" % self.config['rt']['test_resource_dir']):
            if path.isfile(file):
                files.append(unix_path(file))
        ssh.upload(files, self.config['rt']['remote']['test_module_dir'])


class XMLConfigBuilder:
    def __init__(self, templates_dir, config_templates, **kwargs):
        self.templates_dir = templates_dir
        self.config_templates = config_templates
        self.kwargs = kwargs

    def build(self):
        if isinstance(self.config_templates, dict):
            for template, config in self.config_templates.items():
                rendered_string = Environment(loader=FileSystemLoader(self.templates_dir),
                                              trim_blocks=True) \
                    .get_template(template) \
                    .render(self.kwargs)

                with open("%s/%s" % (self.templates_dir, config), "w+") as config_file:
                    config_file.write(rendered_string)
        if isinstance(self.config_templates, list):
            for file in self.config_templates:
                rendered_string = Environment(loader=FileSystemLoader(self.templates_dir),
                                              trim_blocks=True) \
                    .get_template(file) \
                    .render(self.kwargs)

                with open("%s/%s" % (self.templates_dir, file), "w+") as config_file:
                    config_file.write(rendered_string)

