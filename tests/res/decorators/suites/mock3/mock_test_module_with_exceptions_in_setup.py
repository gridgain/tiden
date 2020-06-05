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

from tiden.util import with_setup, log_print
from tiden.tidenexception import TidenException


class MockTestModuleWithExceptionsInSetup:
    def __init__(self, config, ssh_pool):
        pass

    def setup(self):
        raise TidenException('Exception in module setup')

    def teardown(self):
        pass

    def setup_testcase(self):
        log_print('This is mock setup test case')

    def teardown_testcase(self):
        log_print('This is mock teardown test case')

    @with_setup('setup_testcase', 'teardown_testcase')
    def test_should_pass(self):
        log_print('This is just fake test to test Runner!!!')


class MockTestModuleWithGeneralExceptionsInSetup(MockTestModuleWithExceptionsInSetup):
    def setup(self):
        raise Exception('Just General Exception')

