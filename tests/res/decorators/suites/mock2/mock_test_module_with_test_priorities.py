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

from tiden.priority_decorator import test_priority


class MockTestModuleWithTestPriorities:
    """
    Example test class with test priorities. Order of running tests must be HIGH -> NORMAL -> LOW.

    Order of running for tests with same priority is undetermined.

    If you need custom ordering within single priority class, you can use integer priority shifts,
    The order will be, for example: NORMAL(-1) -> NORMAL -> NORMAL(+1).
    """
    method_call_order = 0

    def __init__(self, config, ssh_pool):
        assert 0 == self.method_call_order
        self.method_call_order += 1

    def setup(self):
        assert 1 == self.method_call_order
        self.method_call_order += 1

    # default priority should be NORMAL
    def test_main(self):
        assert self.method_call_order in [4, 5]
        self.method_call_order += 1

    @test_priority.LOW
    def test_2(self):
        assert 8 == self.method_call_order
        self.method_call_order += 1

    @test_priority.HIGH
    def test_1(self):
        assert 2 == self.method_call_order
        self.method_call_order += 1

    @test_priority.LOW(-1)
    def test_5(self):
        assert 7 == self.method_call_order
        self.method_call_order += 1

    @test_priority.NORMAL
    def test_3(self):
        assert self.method_call_order in [4, 5]
        self.method_call_order += 1

    @test_priority.NORMAL(-1)
    def test_6(self):
        assert 3 == self.method_call_order
        self.method_call_order += 1

    @test_priority.LOW(+1)
    def test_4(self):
        assert 9 == self.method_call_order
        self.method_call_order += 1

    @test_priority.LOW(-2)
    def test_7(self):
        assert 6 == self.method_call_order
        self.method_call_order += 1

    def teardown(self):
        assert 10 == self.method_call_order
        self.method_call_order += 1

