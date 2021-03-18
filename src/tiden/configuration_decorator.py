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


def test_configuration(*args):
    def test_configuration_decorator(cls):
        assert len(args) > 0, 'Test configuration is empty'

        args0 = list(args)
        while len(args0) < 3:
            args0.append([])
        configuration_options, configurations, configuration_defaults = args0

        if not configurations:
            configurations = list(
                gen_permutations([
                    [True, False]
                    for configuration_option
                    in configuration_options
                    if configuration_option.endswith('_enabled')
                ])
            )

        assert all(map(
            lambda c: isinstance(c, list),
            (configuration_options, configurations, configuration_defaults)
        )), 'Test configuration accepts only lists'

        cls.__configuration_options__ = configuration_options.copy()
        cls.__configurations__ = configurations.copy()

        if configuration_defaults:
            assert len(configuration_options) == len(configuration_defaults), \
                'Please set defaults for all configuration options'
            cls.__configuration_defaults__ = configuration_defaults.copy()

        return cls
    return test_configuration_decorator
