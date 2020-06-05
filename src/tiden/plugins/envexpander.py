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
from os import environ
from re import compile

from tiden.tidenplugin import TidenPlugin
from tiden.util import log_print, mergedict

TIDEN_PLUGIN_VERSION = '1.0.0'


class EnvExpander(TidenPlugin):
    re_var = compile(r'\${?([A-z\-_a-z0-9]+)}?')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.expand_var_names = self.options.get('expand_vars', [])
        if type(self.expand_var_names) == type(''):
            self.expand_var_names = [self.expand_var_names]
        self.compute_vars = self.options.get('compute_vars', {})
        self.missing_vars = set()

    def after_config_loaded(self, *args, **kwargs):
        input_config = deepcopy(args[0])
        output_config = self._patch_config(input_config)
        return (output_config, *args[1:])

    def _patch_config(self, input_config):
        env = deepcopy(environ)
        output_config = {}
        if len(self.expand_var_names) == 0:
            self._patch_config_with_env(input_config, output_config, env)
        else:
            orig_vars = {}
            for var_name in self.expand_var_names:
                orig_vars[var_name] = env[var_name]
                del env[var_name]
            for var_name in self.expand_var_names:
                var_value = environ.get(var_name, '')
                var_values = var_value.split(',')
                output_config = {}
                if len(var_values) == 0:
                    var_values = ['']
                for var_value in var_values:
                    env[var_name] = var_value
                    tmp_config = {}
                    self._patch_config_with_env(input_config, tmp_config, env)
                    mergedict(tmp_config, output_config)
                del env[var_name]
                input_config = output_config

        for var in self.missing_vars:
            log_print(f'WARN: environment variable {var} referenced in config is not set or empty', color='red')
        return output_config

    def _patch_config_with_env(self, input_config, output_config, env):
        self._compute_env(input_config, env)
        for section_name, section_data in input_config.items():
            new_section_name = self._patch_string(section_name, env)
            output_config[new_section_name] = self._patch_section(section_data, env)

    def _compute_env(self, input_config, env):
        for compute_var_name, compute_var_expr in self.compute_vars.items():
            env[compute_var_name] = self._compute_env_var(compute_var_expr, input_config, env)

    def _compute_env_var(self, expr, c, e):
        return eval(expr, globals(), locals())

    def _patch_string(self, s, env):
        output_string = s
        while '$' in output_string:
            vars = EnvExpander.re_var.finditer(output_string)
            if not vars:
                break
            replaced = False
            for m in vars:
                if not m:
                    continue
                var = m.group(1)
                if var not in env:
                    self.missing_vars.add(var)
                else:
                    val = env.get(var)
                    output_string = output_string[:m.start(0)] + val + output_string[m.end(0):]
                    if var in self.missing_vars:
                        self.missing_vars.remove(var)
                    replaced = True
                    break
            if not replaced:
                break
        return output_string

    def _patch_section(self, s, env):
        if type(s) == type({}):
            result = {}
            for k, v in s.items():
                new_k = self._patch_string(k, env)
                result[new_k] = self._patch_section(v, env)
            return result
        elif type(s) == type(''):
            return self._patch_string(s, env)
        elif type(s) == type([]):
            return s.copy()
        else:
            return s
