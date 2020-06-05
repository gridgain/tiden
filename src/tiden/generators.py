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


def gen_permutations_for_single_list(l):
    for i in l:
        yield [i]


def gen_permutations_for_two_lists(l, r):
    for i in l:
        for j in r:
            yield [i, j]


def gen_glue_two_generated_lists(gen):
    for i in gen:
        c = [i[0]]
        c.extend(i[1])
        yield c


def gen_permutations(l):
    """
    Given list of N lists, generates all N-ary permutations for it
    :param l:
    :return:
    """
    if len(l) == 0:
        return iter([])
    if len(l) == 1:
        return iter(gen_permutations_for_single_list(l[0]))
    if len(l) == 2:
        return iter(gen_permutations_for_two_lists(l[0], l[1]))
    return iter(gen_glue_two_generated_lists(gen_permutations_for_two_lists(l[0], list(gen_permutations(l[1:])))))


def gen_tests(test_class):
    """
    Generates all test method of given test class
    :param test_class:
    :return:
    """
    for class_attr in dir(test_class):
        if class_attr.startswith('test_'):
            yield class_attr

