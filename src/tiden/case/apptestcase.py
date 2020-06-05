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

from ..apps.appscontainer import AppsContainer
from ..apps.app import App
from ..tidenexception import TidenException
from ..util import unix_path
from os.path import isfile
from glob import glob
from ..tidenfabric import TidenFabric
from copy import deepcopy
from ..sshpool import AbstractSshPool


class AppTestCaseContext:

    def __init__(self):
        self.config = TidenFabric().getConfigDict()
        self.ssh: AbstractSshPool = TidenFabric().getSshPool()
        self.apps: AppsContainer = AppsContainer()


class AppTestCase:

    def __init__(self, *args):
        self.tiden: AppTestCaseContext = AppTestCaseContext()

    def add_app(self, app, **kwargs):
        self.tiden.apps.add_app(app, **kwargs)

    def get_app(self, app_name: str) -> App:
        return self.tiden.apps.get_app(app_name)

    def get_app_artifact_name(self, app_name):
        app_opts = self.tiden.apps.get_app_options(app_name)
        return app_opts.get('artifact_name', app_name)

    def setup(self):
        self.tiden.apps.setup_configured_apps(self.tiden.config, self.tiden.ssh)
        self.upload_resources()

    def upload_resources(self):
        files = []
        resources_dir = self.tiden.config['rt']['test_resource_dir']
        for file in glob(f"{resources_dir}/*"):
            if isfile(file):
                files.append(unix_path(file))
        self.tiden.ssh.upload(files, self.tiden.config['rt']['remote']['test_module_dir'])

    def util_exec_on_all_hosts(self, ignite, commands_to_exec):
        commands = {}
        hosts = ignite.config['environment'].get('server_hosts', []) + \
                ignite.config['environment'].get('client_hosts', [])

        for host in hosts:
            if commands.get(host) is None:
                commands[host] = commands_to_exec

        ignite.ssh.exec(commands)

    def teardown(self):
        self.tiden.apps.teardown_running_apps()

    def get_run_info(self):
        run_info = {}
        for app_name in self.tiden.apps.get_running_apps():
            app: App = self.get_app(app_name)
            if hasattr(app, 'get_run_info'):
                run_info = app.get_run_info(run_info)

        return run_info if run_info else None

    def get_app_by_type(self, app_type):
        return self.tiden.apps.get_app_by_type(app_type)

    def create_app_config_set(self, app, config_set_name='default', deploy=False, config_type=None, **variables):
        """
        Create configuration context (a set of configs) for given application,
        generate configs for given context with given values of config variables,
        and optionally deploy generated configs
        :param app: application class
        :param config_set_name: name of config / set of configs
        :param deploy: deploy configs after generation
        :param variables: dictionary of variables
        :param config_type: config type (for example: 'client', 'server')
        :return:
        """

        if not hasattr(app, 'config_builder') or not app.config_builder:
            assert hasattr(app, 'create_config_builder'), f"Not an App: {app}"
            app.create_config_builder(self.tiden.ssh, self.tiden.config)

        # 1. Register config if needed
        app.config_builder.register_config_set(config_set_name)
        # 1.1. Add configs
        if 'additional_configs' in variables:
            for config_name in variables['additional_configs']:
                config_t = config_name.split('.')[0]
                app.config_builder.add_config_type(config_t, config_name, config_set_name)
        # 2. Add variables to previously registered config
        app.config_builder.add_template_variables(config_set_name, **variables)
        # 3. Build and maybe deploy config on hosts
        if deploy:
            app.config_builder.build_config_and_deploy(config_set_name=config_set_name, config_type=config_type)
        else:
            app.config_builder.build_config(config_set_name=config_set_name, config_type=config_type)

    def remove_app_config_set(self, app, config_set_name):
        if not hasattr(app, 'config_builder') or not app.config_builder:
            return

        app.config_builder.unregister_config_set(config_set_name)

    def check_requirements(self):
        return self.tiden.apps.check_requirements(self.tiden.config, self.tiden.ssh)

