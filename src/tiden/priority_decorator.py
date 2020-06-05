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

from enum import IntEnum
from .tidenexception import TidenException
from functools import cmp_to_key


class Priorities(IntEnum):
    LOW = +100000
    NORMAL = 0
    HIGH = -100000


def get_priority_key(test_class):
    """
    key function to enforce ordering on test methods of given test class
    :param test_class: Tiden TestCase object instance
    :return: function to be passed to `sorted` via key argument
    """

    def priority_comparator(test_name_a, test_name_b):
        test_name_a = test_name_a.split('(')[0] if '(' in test_name_a else test_name_a
        test_name_b = test_name_b.split('(')[0] if '(' in test_name_b else test_name_b
        test_a = getattr(test_class, test_name_a)
        test_b = getattr(test_class, test_name_b)
        priority_a = int(Priorities.NORMAL) if not hasattr(test_a, '__priority__') else getattr(test_a, '__priority__')
        priority_b = int(Priorities.NORMAL) if not hasattr(test_b, '__priority__') else getattr(test_b, '__priority__')
        if priority_a < priority_b:
            return -1
        if priority_a > priority_b:
            return 1
        if test_name_a < test_name_b:
            return -1
        if test_name_a > test_name_b:
            return 1
        # we definitely could not get tests with same names
        raise TidenException("Tests %s and %s can't be compared!" % (test_name_a, test_name_b))

    return cmp_to_key(priority_comparator)


def uncarr(priority_level):
    def prcurr(arg):
        if type(arg) == type(42):
            priority_shift = arg

            def test_priority_decorator(func):
                func.__priority__ = int(priority_level) + priority_shift
                return func

            return test_priority_decorator
        else:
            func = arg
            func.__priority__ = int(priority_level)
            return func

    return prcurr

test_priority = uncarr(Priorities.NORMAL)
test_priority.LOW = uncarr(Priorities.LOW)
test_priority.NORMAL = uncarr(Priorities.NORMAL)
test_priority.HIGH = uncarr(Priorities.HIGH)

