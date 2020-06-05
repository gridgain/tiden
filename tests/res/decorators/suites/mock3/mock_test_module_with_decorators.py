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

from tiden.util import attr, with_setup, log_print, repeated_test
from tiden.tidenexception import TidenException
import inspect


class MockTestModuleWithDecorators:
    def __init__(self, config, ssh_pool):
        self.count = 0
        self.iteration = 0
        self.config = config
        self.current_test = None

    def setup_testcase(self):
        log_print('This is mock setup test case')

    def teardown_testcase(self):
        log_print('This is mock teardown test case')

    @with_setup(setup_testcase, teardown_testcase)
    def test_not_repeated_test(self):
        log_print('This is just fake test to test repeated decorator!!!')
        self._mock_test_execution(method_name=inspect.stack()[0].function)

    @repeated_test(2)
    @with_setup(setup_testcase, teardown_testcase)
    def test_repeated_test(self):
        log_print('This is just fake test to test repeated decorator!!!')
        self._mock_test_execution(method_name=inspect.stack()[0].function)

    @repeated_test(2, test_names=['example'])
    @with_setup(setup_testcase, teardown_testcase)
    def test_with_repeated_test_and_not_full_test_names(self):
        log_print('This is just fake test to test repeated decorator!!!')
        self._mock_test_execution(method_name=inspect.stack()[0].function)

    @repeated_test(2, test_names=['first', 'second'])
    @with_setup(setup_testcase, teardown_testcase)
    def test_with_repeated_test_and_full_test_names(self):
        log_print('This is just fake test to test repeated decorator!!!')
        self._mock_test_execution(method_name=inspect.stack()[0].function)

    @repeated_test(4, test_names=['first', 'second'])
    @with_setup(setup_testcase, teardown_testcase)
    def test_with_repeated_test_and_fail_on_iteration_3(self):
        log_print('This is just fake test to test repeated decorator!!!')
        self._mock_test_execution(method_name=inspect.stack()[0].function)
        self.count += 1

        if self.count == 3:
            raise TidenException('Exception on iteration 3')

    def _mock_test_execution(self, method_name=None):
        if method_name and method_name != self.current_test:
            self.iteration = 1
            self.current_test = method_name
        else:
            self.iteration += 1
        log_file = '{}/{}_iteration_{}.log'.format(self.config['rt']['remote'].get('test_dir'),
                                                   self.config['rt']['test_method'],
                                                   self.iteration)
        with open(log_file, "w") as log:
            log.write('{} test execution'.format(self.config['rt']['test_method']))

