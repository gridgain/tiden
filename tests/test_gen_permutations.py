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

from tiden.generators import gen_permutations, gen_permutations_for_single_list, gen_permutations_for_two_lists


def test_gen_permutations_for_single_list_1():
    res = list(gen_permutations_for_single_list([]))
    print(res)
    assert 0 == len(res)


def test_gen_permutations_for_single_list_2():
    res = list(gen_permutations_for_single_list([1]))
    print(res)
    assert 1 == len(res)
    assert [1] in res


def test_gen_permutations_for_single_list_3():
    res = list(gen_permutations_for_single_list([1, 2]))
    print(res)
    assert 2 == len(res)
    assert [1] in res
    assert [2] in res


def test_gen_permutations_for_two_lists_1():
    res = list(gen_permutations_for_two_lists([], []))
    print(res)
    assert 0 == len(res)


def test_gen_permutations_for_two_lists_2():
    res = list(gen_permutations_for_two_lists([], [1]))
    print(res)
    assert 0 == len(res)


def test_gen_permutations_for_two_lists_3():
    res = list(gen_permutations_for_two_lists([1], [1]))
    print(res)
    assert 1 == len(res)
    assert [1, 1] in res


def test_gen_permutations_for_two_lists_4():
    res = list(gen_permutations_for_two_lists([1, 2], [1]))
    print(res)
    assert 2 == len(res)
    assert [1, 1] in res
    assert [2, 1] in res


def test_gen_permutations_for_two_lists_5():
    res = list(gen_permutations_for_two_lists([1], [1, 2]))
    print(res)
    assert 2 == len(res)
    assert [1, 1] in res
    assert [1, 2] in res


def test_gen_permutations_for_two_lists_6():
    res = list(gen_permutations_for_two_lists([1, 2], [1, 2]))
    print(res)
    assert 4 == len(res)
    assert [1, 1] in res
    assert [1, 2] in res
    assert [2, 1] in res
    assert [2, 2] in res


def test_gen_permutations_for_two_lists_7():
    res = list(gen_permutations_for_two_lists([1, 2, 3], [1, 2]))
    print(res)
    assert 6 == len(res)
    assert [1, 1] in res
    assert [1, 2] in res
    assert [2, 1] in res
    assert [2, 2] in res
    assert [3, 1] in res
    assert [3, 2] in res


def test_gen_permutations_1():
    res = list(gen_permutations([]))
    print(res)
    assert 0 == len(res)


def test_gen_permutations_2():
    res = list(gen_permutations([[]]))
    print(res)
    assert 0 == len(res)


def test_gen_permutations_3():
    res = list(gen_permutations([[1]]))
    print(res)
    assert 1 == len(res)
    assert [1] in res


def test_gen_permutations_4():
    res = list(gen_permutations([[1, 2, 3]]))
    print(res)
    assert 3 == len(res)
    assert [1] in res
    assert [2] in res
    assert [3] in res


def test_gen_permutations_5():
    res = list(gen_permutations([[1, 2, 3], [5, 6]]))
    print(res)
    assert 6 == len(res)
    assert [1, 5] in res
    assert [2, 5] in res
    assert [3, 5] in res
    assert [1, 6] in res
    assert [2, 6] in res
    assert [3, 6] in res


def test_gen_permutations_6():
    res = list(gen_permutations([[1, 2, 3], [5, 6], [8, 9]]))
    print(res)
    assert 12 == len(res)
    assert [1, 5, 8] in res
    assert [1, 5, 9] in res
    assert [1, 6, 8] in res
    assert [1, 6, 9] in res
    assert [2, 5, 8] in res
    assert [2, 5, 9] in res
    assert [2, 6, 8] in res
    assert [2, 6, 9] in res
    assert [3, 5, 8] in res
    assert [3, 5, 9] in res
    assert [3, 6, 8] in res
    assert [3, 6, 9] in res

