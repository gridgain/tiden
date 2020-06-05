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

from tiden import log_print, TidenException


class AppConfigBuilder:
    """
    Holds a dictionary of configuration sets for given application.
    Each configuration set holds a set of config files of different type (e.g. server config, client config).
    """
    current_config_set = None

    def __init__(self, tiden_ssh, tiden_config, app):
        self.tiden_ssh = tiden_ssh
        self.tiden_config = tiden_config

        self.app = app

        self.config_sets = {}

    def register_config_set(self, config_set_name):
        """
        Register new config set

        Context name:
        * common variables - variables for all configs in this context
        * exclusive variables - variables for particular node
        * common configs - result of config + common variables
        * exclusive configs - result of exclusive config + (common + exclusive variables)

        :param config_set_name: configuration set name
        :return:
        """
        if config_set_name in self.config_sets:
            log_print("Config set with name '%s' is already registered. Creating new config set." % config_set_name,
                      color='yellow')

        self.config_sets[config_set_name] = {}

        if self.current_config_set is None:
            self.current_config_set = config_set_name

        self.config_sets[config_set_name]['common_variables'] = {}
        self.config_sets[config_set_name]['exclusive_variables'] = {}
        self.config_sets[config_set_name]['common_configs'] = {}
        self.config_sets[config_set_name]['exclusive_configs'] = {}
        self.config_sets[config_set_name]['additional_config_types'] = {}
        return self.config_sets[config_set_name]

    def cleanup_exclusive_configs(self):
        for config in self.config_sets.keys():
            self.config_sets[config]['exclusive_variables'] = {}
            self.config_sets[config]['exclusive_configs'] = {}

    def unregister_config_set(self, config_set_name):
        if config_set_name not in self.config_sets:
            log_print("Unknown config set '%s' to remove" % config_set_name)
            return

        del self.config_sets[config_set_name]

    def add_template_variables(self, config_set_name=None, node_id=None, **values):
        if config_set_name is None:
            insert_config_list = [self.current_config_set]
        else:
            if config_set_name not in ['*', 'all']:
                if config_set_name not in self.config_sets:
                    raise TidenException('Unknown config set name! Currently created configs: %s' %
                                         str(self.config_sets.keys()))

                insert_config_list = [config_set_name]
            else:
                insert_config_list = self.config_sets.keys()

        for cfg_set_name in insert_config_list:
            if node_id:
                # insert exclusive config variables
                if node_id not in self.config_sets[cfg_set_name]['exclusive_variables']:
                    self.config_sets[cfg_set_name]['exclusive_variables'][node_id] = values
                else:
                    self.config_sets[cfg_set_name]['exclusive_variables'][node_id] = \
                        {**self.config_sets[cfg_set_name]['exclusive_variables'][node_id], **values}
            else:
                # insert common variables
                self.config_sets[cfg_set_name]['common_variables'] = {**self.config_sets[config_set_name]['common_variables'], **values}

    def get_template_variables(self, node_id=None, config_set_name=None):
        cfg_set_name = self.__get_config_set_name(config_set_name)

        if node_id:
            # get exclusive config
            # there is no such node - return common variables
            if node_id not in self.config_sets[cfg_set_name]['exclusive_variables']:
                return self.config_sets[cfg_set_name]['common_variables']
            else:
                # otherwise get merged common and exclusive variables
                return {**self.config_sets[cfg_set_name]['exclusive_variables'][node_id],
                        **self.config_sets[cfg_set_name]['common_variables']}
        else:
            # get common config
            return self.config_sets[cfg_set_name]['common_variables']

    def __get_config_set_name(self, config_set_name):
        cfg_set_name = config_set_name if config_set_name else self.current_config_set
        if cfg_set_name is None or cfg_set_name not in self.config_sets:
            raise TidenException(f'Unknown configuration set name: {cfg_set_name}! '
                                 f'Currently created config sets: {self.config_sets.keys()}')
        return cfg_set_name

    def get_config(self, config_type, config_set_name=None, node_id=None):
        """
        Get actual config file name for given config type
        :param config_type:
        :param config_set_name:
        :param node_id:
        :return:
        """
        cfg_set_name = self.__get_config_set_name(config_set_name)

        if node_id:
            # get exclusive config
            if node_id not in self.config_sets[cfg_set_name]['exclusive_configs']:
                raise TidenException("Unknown node_id '%s' in exclusive config set '%s'" % (node_id, config_set_name))

            if config_type not in self.config_sets[cfg_set_name]['exclusive_configs'][node_id]:
                raise TidenException("Unknown config_type '%s' in exclusive config set '%s' for node %s" %
                                     (config_type, cfg_set_name, node_id))

            return self.config_sets[cfg_set_name]['exclusive_configs'][node_id][config_type]
        else:
            # get common config
            if config_type not in self.config_sets[cfg_set_name]['common_configs']:
                raise TidenException("Unknown config type '%s', maybe per_node_config used." % config_type)

            return self.config_sets[cfg_set_name]['common_configs'][config_type]

    def add_config_type(self, config_type, config_name, config_set_name=None):
        # for all registered configs generate files
        for cfg_set_name, cfg_set in self.config_sets.items():
            # skip generating configs not in filter
            if config_set_name and cfg_set_name != config_set_name:
                continue

            cfg_set['additional_config_types'][config_type] = config_name

    def build_config(self, config_type=None, config_set_name=None, node_id=None):
        """
        Build config files, either for all configuration sets or specific one.
        :param config_type: (optional) build specific configuration file instead of all set
        :param config_set_name: (optional) configuration set to build config files
        :param node_id: (optional) build configuration files exclusive for that node id
        :return:
        """
        # for all registered configs generate files
        for cfg_set_name, cfg_set in self.config_sets.items():
            # skip generating configs not in filter
            if config_set_name and cfg_set_name != config_set_name:
                continue

            dict_configs = {}
            config_types = {}
            config_types.update(self.app.get_config_types())
            config_types.update(cfg_set['additional_config_types'])

            # for each item in app.get_config() define generated config name (client, server in Ignite e.g.)
            for cfg_type, original_config in config_types.items():
                # skip generating configs not in filter
                if config_type and cfg_type != config_type:
                    continue

                if not node_id:
                    # generate common config
                    generated_config_name = original_config.replace('.tmpl', '_%s' % cfg_set_name)

                    # generate mapping {template: result} file name for XMLConfigBuilder
                    dict_configs[original_config] = generated_config_name

                    # remember result file name
                    cfg_set['common_configs'][cfg_type] = generated_config_name
                else:
                    # generate exclusive config
                    generated_config_name = original_config.replace('.tmpl', '_%s_%s' % (cfg_set_name, node_id))

                    # generate mapping {template: result} file name for XMLConfigBuilder
                    dict_configs[original_config] = generated_config_name

                    # remember result file name
                    if node_id not in cfg_set['exclusive_configs']:
                        cfg_set['exclusive_configs'][node_id] = {}

                    cfg_set['exclusive_configs'][node_id][cfg_type] = generated_config_name

            # define variables for configs
            if node_id and node_id in cfg_set['exclusive_variables']:
                variables = {**cfg_set['common_variables'],
                             **cfg_set['exclusive_variables'][node_id]}
            else:
                variables = cfg_set['common_variables']

            # render template
            for template, config in dict_configs.items():
                rendered_string = Environment(loader=FileSystemLoader(self.tiden_config['rt']['test_resource_dir']),
                                              trim_blocks=True) \
                    .get_template(template) \
                    .render({**variables, **self.tiden_config})

                with open("%s/%s" % (self.tiden_config['rt']['test_resource_dir'], config), "w+") as config_file:
                    config_file.write(rendered_string)

    def build_config_and_deploy(self, config_type=None, config_set_name=None, node_id=None):
        from glob import glob
        from os import path
        from tiden.util import unix_path

        if isinstance(config_type, (list, tuple)):
            for type in config_type:
                self.build_config(type, config_set_name, node_id)
        else:
            self.build_config(config_type, config_set_name, node_id)
        files = []
        test_resource_dir = self.tiden_config['rt']['test_resource_dir']
        for file in glob(f"{test_resource_dir}/*"):
            if path.isfile(file):
                files.append(unix_path(file))
        self.tiden_ssh.upload(files, self.tiden_config['rt']['remote']['test_module_dir'])

    def __str__(self):
        res = ['\nApplication config for app %s:\n' % str(self.app.__name__),
               '\n  Current config set: %s\n' % self.current_config_set,
               '\n  Original configs: %s\n' % self.app.get_config_types()]

        for config_set_name in self.config_sets:
            res.append('\n  Config set: %s\n' % config_set_name)
            res.append('    Common template variables: %s\n' % self.config_sets[config_set_name]['common_variables'])
            res.append('    Exclusive template variables: %s\n' % self.config_sets[config_set_name]['exclusive_variables'])
            res.append('    Common generated configs: %s\n' % self.config_sets[config_set_name]['common_configs'])
            res.append('    Exclusive generated configs: %s\n' % self.config_sets[config_set_name]['exclusive_configs'])

        return ''.join(res)
