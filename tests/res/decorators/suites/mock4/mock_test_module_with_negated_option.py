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

from tiden.configuration_decorator import test_configuration
from tiden.util import require
from tiden.testconfig import test_config
from time import sleep


class MockTestModuleWithNegatedOption:
    """
    Example test class with few boolean configuration options checked via `@require`.
    Options are detected as boolean when their name ends with '_enabled'.
    """
    def __init__(self, config, ssh_pool):
        pass

    def test_main(self):
        pass

    @require(~test_config.zookeeper_enabled)
    def test_without_zookeeper_only(self):
        pass

    @require(test_config.zookeeper_enabled)
    def test_with_zookeeper_only(self):
        pass

    def teardown(self):
        pass

