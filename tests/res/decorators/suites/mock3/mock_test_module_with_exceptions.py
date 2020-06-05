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

from tiden.util import attr, with_setup, log_print, require
from tiden.tidenexception import TidenException


class MockTestModuleWithExceptions:
    def __init__(self, config, ssh_pool):
        pass

    def setup_testcase(self):
        log_print('This is mock setup test case')

    def teardown_testcase(self):
        log_print('This is mock teardown test case')

    def setup_testcase_with_exception(self):
        self.setup_testcase()
        raise TidenException('Exception in test setup')

    def teardown_testcase_with_exception(self):
        self.teardown_testcase()
        raise TidenException('Exception in test teardown')

    @attr('test_runner')
    @with_setup(setup_testcase, teardown_testcase)
    def test_should_pass(self):
        log_print('This is just fake test to test Runner!!!')

    @attr('test_runner')
    @require(False)
    def test_should_be_skipped(self):
        log_print('This message should not be in the output: CHUMSCRUBBER.')

    @attr('test_runner')
    @with_setup(setup_testcase, teardown_testcase)
    def test_passed_with_result_message(self):
        log_print('This mega test should print WOO-HOO in report message')
        log_print('WOO-HOO', report=True)

    @attr('test_runner')
    @with_setup(setup_testcase, teardown_testcase)
    def test_should_fail(self):
        log_print('This is just fake test with exception to test Runner!!!')
        raise TidenException('Fake exception in test')

    @attr('test_runner')
    @with_setup(setup_testcase, teardown_testcase)
    def test_should_fail_with_error(self):
        log_print('This is just fake test with not Tiden exception to test Runner!!!')
        raise IOError('Fake IO exception in test')

    @attr('test_runner')
    @with_setup(setup_testcase_with_exception, teardown_testcase)
    def test_with_exception_in_setup(self):
        log_print('This is just fake test with exception to test Runner!!!')
        raise TidenException('Fake exception in test')

    @attr('test_runner')
    @with_setup(setup_testcase, teardown_testcase_with_exception)
    def test_pass_with_exception_in_teardown(self):
        log_print('This is just fake test with exception to test Runner!!!')

    @attr('test_runner')
    @with_setup(setup_testcase, teardown_testcase_with_exception)
    def test_fail_with_exception_in_teardown(self):
        log_print('This is just fake test with exception to test Runner!!!')
        raise TidenException('Fake exception in test')

    @attr('not matching')
    def test_should_be_not_started(self):
        log_print('you should never see CHUMSCRUBBER in logs of this test')

