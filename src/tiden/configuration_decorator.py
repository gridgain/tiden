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


def test_configuration(*args):
    def test_configuration_decorator(cls):
        assert len(args) > 0
        if len(args) >= 1:
            configuration_options = args[0]
        if len(args) >= 2:
            configurations = args[1]
        else:
            configurations = list(
                gen_permutations([
                    [True, False]
                    for configuration_option
                    in configuration_options
                    if configuration_option.endswith('_enabled')
                ])
            )
        cls.__configuration_options__ = configuration_options.copy()
        cls.__configurations__ = configurations.copy()
        return cls
    return test_configuration_decorator

