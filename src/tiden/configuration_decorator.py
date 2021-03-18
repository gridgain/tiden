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

from .generators import gen_permutations

CONFIG_NOT_APPLICABLE_OPTION = 'CONFIG_NOT_APPLICABLE_OPTION'


class test_configuration:
    def __init__(self, options: list, possible_values: list = None, default_values: list = None):
        assert options, 'Test configuration is empty'

        self.options = options
        self.possible_values = possible_values
        self.default_values = default_values

        if not self.possible_values:
            self.possible_values = list(
                gen_permutations([
                    [True, False]
                    for configuration_option
                    in options
                    if configuration_option.endswith('_enabled')
                ])
            )

        assert isinstance(self.possible_values, list) and isinstance(self.possible_values, list), \
            'Test configuration accepts only lists'

        if self.default_values:
            assert isinstance(self.default_values, list), 'Test configuration accepts only lists'
            assert len(self.default_values) == len(self.options), 'Please set defaults for all configuration options'

    def __call__(self, cls):
        cls.__configuration_options__ = self.options
        cls.__configurations__ = self.possible_values
        if self.default_values:
            cls.__configuration_defaults__ = self.default_values

        return cls
