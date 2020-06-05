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

import pytest
from tiden.case.generaltestcase import GeneralTestCase
from tiden.assertions import tiden_assert, tiden_assert_equal, tiden_assert_is_none, tiden_assert_is_not_none


def mock_testcase(tmpdir, testcase_class, config_ext={}):
    class MockSsh:
        hosts = []

    class_name = testcase_class.__name__.lower()
    var_dir = tmpdir.mkdir('var-'+class_name)
    config_path = var_dir.join('config.yaml')
    mockConfig = {
        'rt': {
            'test_module_dir': str(var_dir),
            'test_module': 'mock.' + class_name,
            'resource_dir': str(var_dir),
        },
        'environment': {'server_hosts': "127.0.0.1", "client_hosts": "127.0.0.1"},
        'config_path': str(config_path),
        'suite_dir': str(var_dir.join('suite')),
    }
    mockConfig.update(config_ext)
    mockSsh = MockSsh()
    return testcase_class(mockConfig, mockSsh)


def test_create_general_testcase(tmpdir):
    testcase = mock_testcase(tmpdir, GeneralTestCase)
    class_name = 'generaltestcase'
    assert str(tmpdir.join('var'+'-'+class_name).join('suite')) == testcase.get_suite_dir(), "suite_dir"
    assert set(['default']) == set(testcase.get_contexts()), "default context present"

    new_context = testcase.create_test_context('new')
    assert new_context is not None
    assert set(['new', 'default']) == set(testcase.get_contexts()), "new context present"


def test_assert():
    tiden_assert(True, 'ok')
    with pytest.raises(AssertionError):
        tiden_assert(False, 'fail')


def test_assert_equal():
    tiden_assert_equal(2, 2, '2==2')
    with pytest.raises(AssertionError):
        tiden_assert_equal(2, 1, '2==1')


def test_assert_is_none():
    tiden_assert_is_none(None, 'ok')
    with pytest.raises(AssertionError):
        tiden_assert_is_none(False, 'fail')


def test_assert_is_not_none():
    tiden_assert_is_not_none(True, 'ok')
    with pytest.raises(AssertionError):
        tiden_assert_is_not_none(None, 'fail')


def test_require_min_server_nodes(tmpdir):
    from tiden.util import require_min_server_nodes

    class MyTestCase(GeneralTestCase):
        @require_min_server_nodes(4)
        def test_1(self):
            pass

    test_config_should_pass = {
        'environment': {
            'server_hosts': [
                '127.0.0.1',
            ],
            'servers_per_host': 4,
        }
    }
    test_config_should_fail = {
        'environment': {
            'server_hosts': [
                '127.0.0.1',
            ],
            'servers_per_host': 1,
        }
    }

    m = mock_testcase(tmpdir, MyTestCase)
    assert not hasattr(m.test_1, '__skip_conds__')
    assert hasattr(m.test_1, '__skip_cond__')

    res, msg = m.test_1.__skip_cond__(test_config_should_pass)
    assert res
    assert "Minimum server nodes must be 4" == msg

    res, msg = m.test_1.__skip_cond__(test_config_should_fail)
    assert not res
    assert "Minimum server nodes must be 4" == msg


def test_require_single_requirement(tmpdir):
    from tiden.util import require

    class MyTestCase(GeneralTestCase):
        @require(min_server_nodes=4)
        def test_1(self):
            pass

        @require(min_ignite_version='2.4.2-p4')
        def test_2(self):
            pass

        @require(min_server_nodes=1, min_ignite_version='2.4.2-p2')
        def test_3(self):
            pass

    test_config = {
        'environment': {
            'server_hosts': [
                '127.0.0.1',
            ],
            'servers_per_host': 1,
        },
        'artifacts': {
            'ignite': {
                'type': 'ignite',
                'ignite_version': '2.4.2-p2'
            }
        },
    }

    m = mock_testcase(tmpdir, MyTestCase, test_config)

    assert not hasattr(m.test_1, '__skip_cond__')
    assert hasattr(m.test_1, '__skip_conds__')
    assert 1 == len(m.test_1.__skip_conds__)

    res, msg = m.test_1.__skip_conds__[0](m)
    assert not res
    assert "Minimum server nodes must be 4" == msg

    assert not hasattr(m.test_2, '__skip_cond__')
    assert hasattr(m.test_2, '__skip_conds__')
    assert 1 == len(m.test_2.__skip_conds__)

    res, msg = m.test_2.__skip_conds__[0](m)
    assert not res
    assert "Ignite version < 2.4.2-p4" == msg

    assert not hasattr(m.test_3, '__skip_cond__')
    assert hasattr(m.test_3, '__skip_conds__')
    assert 2 == len(m.test_3.__skip_conds__)

    res, msg = m.test_3.__skip_conds__[0](m)
    assert res
    res, msg = m.test_3.__skip_conds__[1](m)
    assert res


def test_require_config_args(tmpdir):
    from tiden.util import require
    from tiden.testconfig import test_config
    test_config.obj = {}

    some_shit = False

    class AnotherTestCase(GeneralTestCase):
        @require(some_shit)
        def test_0(self):
            pass

        @require(test_config.ignite.pitr_enabled)
        def test_1(self):
            pass

    m = mock_testcase(tmpdir, AnotherTestCase)

    assert not hasattr(m.test_0, '__skip_cond__')
    assert hasattr(m.test_0, '__skip_conds__')
    assert 1 == len(m.test_0.__skip_conds__)

    assert not hasattr(m.test_1, '__skip_cond__')
    assert hasattr(m.test_1, '__skip_conds__')
    assert 1 == len(m.test_1.__skip_conds__)

    res, msg = m.test_0.__skip_conds__[0](m)
    assert not res
    assert msg.startswith('expression evaluates to False')
    # print(msg)

    res, msg = m.test_1.__skip_conds__[0](m)
    assert not res
    assert "config.ignite.pitr_enabled is None" == msg


def test_require_negative_config_args(tmpdir):
    from tiden.util import require
    from tiden.testconfig import test_config
    test_config.obj = {
        'share_enabled': False,
    }

    class MixSharedTestCase(GeneralTestCase):
        @require(test_config.share_enabled)
        def test_1(self):
            pass

        @require(~test_config.share_enabled)
        def test_2(self):
            pass

    m = mock_testcase(tmpdir, MixSharedTestCase)

    assert not hasattr(m.test_1, '__skip_cond__')
    assert hasattr(m.test_1, '__skip_conds__')
    assert 1 == len(m.test_1.__skip_conds__)

    assert not hasattr(m.test_2, '__skip_cond__')
    assert hasattr(m.test_2, '__skip_conds__')
    assert 1 == len(m.test_2.__skip_conds__)

    res, msg = m.test_1.__skip_conds__[0](m)
    assert not res
    assert "config.share_enabled is False" == msg

    res, msg = m.test_2.__skip_conds__[0](m)
    assert res
    assert "config.share_enabled is True" == msg

    test_config.obj = {
        'another_share_enabled': True,
    }

    attr = test_config.another_share_enabled
    not_attr = ~ test_config.another_share_enabled

    class MixSharedTestCase2(GeneralTestCase):
        @require(test_config.another_share_enabled)
        def test_1(self):
            pass

        @require(~test_config.another_share_enabled)
        def test_2(self):
            pass

    m1 = mock_testcase(tmpdir, MixSharedTestCase2)

    assert not hasattr(m1.test_1, '__skip_cond__')
    assert hasattr(m1.test_1, '__skip_conds__')
    assert 1 == len(m1.test_1.__skip_conds__)

    assert not hasattr(m1.test_2, '__skip_cond__')
    assert hasattr(m1.test_2, '__skip_conds__')
    assert 1 == len(m1.test_2.__skip_conds__)

    res, msg = m1.test_1.__skip_conds__[0](m)
    assert res
    assert "config.another_share_enabled" == msg

    res, msg = m1.test_2.__skip_conds__[0](m)
    assert not res
    assert "config.another_share_enabled is True" == msg

