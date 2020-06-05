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

from os.path import join, dirname, basename, exists
from tiden.localpool import LocalPool
from copy import deepcopy
from tiden.tidenrunner import TidenRunner
from tiden.util import read_yaml_file


def test_runner_empty():
    tr = TidenRunner({}, ssh_pool=None, modules={})
    assert 0 == tr.long_path_len
    tr.collect_tests()


def _ensure_xunit_file_empty(var_dir, suffix=''):
    xunit_file = var_dir.join('xunit%s.xml' % suffix)
    xunit_file.write('', ensure=True)
    return str(xunit_file)


def _ensure_var_dir(tmpdir):
    var_dir = str(tmpdir.mkdir('var'))
    print("Var directory: %s" % str(var_dir))
    return tmpdir.join('var')


def _ensure_tr_report_file_empty(var_dir, suffix=''):
    tr_file = var_dir.join('testrail_report%s.yaml' % suffix)
    tr_file.write('', ensure=True)
    return str(tr_file)


def test_runner_collect(with_dec_classpath, local_config, tmpdir, mock_pm):
    var_dir = _ensure_var_dir(tmpdir)
    xunit_file_collect = _ensure_xunit_file_empty(var_dir, '-collect')
    xunit_file_process = _ensure_xunit_file_empty(var_dir, '-process')
    testrail_report_file_collect = _ensure_tr_report_file_empty(var_dir, '-collect')
    testrail_report_file_process = _ensure_tr_report_file_empty(var_dir, '-process')

    suite_var_dir = str(var_dir.mkdir('suite-mock'))
    config_path = str(var_dir.join('config.yaml'))

    source = 'mock_test_module_with_test_configuration'
    suite = 'mock'
    module_name = 'suites.%s.%s.MockTestModuleWithTestConfiguration' % (suite, source)
    test_prefix = module_name + '.'

    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        'suite_var_dir': suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': suite_var_dir,
        },
        'config_path': config_path,
        'zookeeper_enabled': False,
        'pitr_enabled': False,
        'compaction_enabled': True,
    })

    ssh_pool = LocalPool(local_config['ssh'])
    test_module_source_file_name = '%s/%s/%s.py' % (config['suite_dir'], suite, source)

    modules = {
        '%s.%s' % (suite, source): {
            'path': test_module_source_file_name,
            'module_short_name': source,
        }
    }
    test_configuration = '(pitr_enabled=false, compaction_enabled=true, zookeeper_enabled=false)'
    expected_configuration_options = ['pitr_enabled', 'compaction_enabled', 'zookeeper_enabled']
    expected_result = {
        'test_main':
            {'status': 'pass', 'type': None, 'message': None},
        'test_zookeeper_only':
            {'status': 'skipped', 'type': 'skipped cause of config.zookeeper_enabled is None', 'message': None},
    }

    from tiden.tidenfabric import TidenFabric
    TidenFabric().reset().setConfig(config)

    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file_collect)
    tr.collect_tests()
    res = tr.get_tests_results()
    res.update_xunit()
    res.create_testrail_report(config, report_file=basename(testrail_report_file_collect))
    _tests = res.get_tests()
    assert 12 == len(_tests)
    print(_tests)

    TidenFabric().reset().setConfig(config)
    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file_process)
    tr.process_tests()
    res = tr.get_tests_results()
    res.create_testrail_report(config, report_file=basename(testrail_report_file_process))
    _tests = res.get_tests()
    assert 2 == len(_tests)
    print(_tests)


def test_runner_basic(with_dec_classpath, local_config, tmpdir, mock_pm):
    """
    Just test that after TidenRunner execution we've got correct test results ans correct exceptions in the
    failed tests.
    :return:
    """
    var_dir = _ensure_var_dir(tmpdir)
    xunit_file = _ensure_xunit_file_empty(var_dir)
    testrail_report_file = _ensure_tr_report_file_empty(var_dir)

    suite_var_dir = str(var_dir.mkdir('suite-mock'))
    config_path = str(var_dir.join('config.yaml'))
    suite = 'mock3'
    module_short_name = 'mock_test_module_with_exceptions'
    module_class_name = 'MockTestModuleWithExceptions'
    module_name = 'suites.%s.%s.%s' % (suite, module_short_name, module_class_name)
    test_prefix = module_name + '.'

    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        'attrib': 'test_runner',
        'attr_match': 'any',
        'suite_var_dir': suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': suite_var_dir,
        },
        'config_path': config_path,
    })

    ssh_pool = LocalPool(local_config['ssh'])
    test_module_source_file_name = '%s/%s/%s.py' % (config['suite_dir'], suite, module_short_name)

    modules = {
        '%s.%s' % (suite, module_short_name): {
            'path': test_module_source_file_name,
            'module_short_name': module_short_name,
        }
    }
    expected_result = {
        'test_should_pass':
            {'status': 'pass', 'type': None, 'message': None},
        'test_passed_with_result_message':
            {'status': 'pass', 'type': None, 'message': 'WOO-HOO'},
        'test_should_fail':
            {'status': 'fail', 'type': 'TidenException', 'message': 'TidenException(\'Fake exception in test\')'},
        'test_should_be_skipped':
            {'status': 'skipped',
             'type': 'skipped cause of expression evaluates to False at %s:45' % test_module_source_file_name,
             'message': None},
        'test_should_be_not_started':
            {'status': 'skipped_no_start',
             'type': 'skipped cause of attrib mismatch',
             'message': None},
        'test_with_exception_in_setup':
            {'status': 'fail', 'type': 'TidenException', 'message': 'TidenException(\'Exception in test setup\')'},
        'test_pass_with_exception_in_teardown':
            {'status': 'pass', 'type': None, 'message': None},
        'test_fail_with_exception_in_teardown':
            {'status': 'fail', 'type': 'TidenException', 'message': 'TidenException(\'Fake exception in test\')'},
        'test_should_fail_with_error':
            {'status': 'error', 'type': 'OSError', 'message': 'IOError(\'Fake IO exception in test\')'},
    }

    expected_statuses_count = {'pass': 3,
                               'fail': 3,
                               'error': 1,
                               'skip': 2,
                               'total': len(expected_result)}

    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    tr.process_tests()
    res = tr.get_tests_results()
    _tests = res.get_tests()
    print(_tests)

    # validate raw test results
    assert len(_tests) == len(expected_result)

    for test_to_check in expected_result.keys():
        status, error_type, message, test_name = res.get_test_details('{}{}'.format(test_prefix, test_to_check))
        assert expected_result[test_to_check].get('status') == status
        assert expected_result[test_to_check].get('type') == error_type
        if expected_result[test_to_check].get('message') is None:
            assert message is None
        else:
            assert expected_result[test_to_check].get('message') == message \
                   or expected_result[test_to_check].get('message') in message

    for status, count in expected_statuses_count.items():
        assert res.get_tests_num(status) == count

    # validate generated TestRail .yaml report
    res.create_testrail_report(config, report_file=basename(testrail_report_file))
    tr_report = read_yaml_file(testrail_report_file)
    assert type({}) == type(tr_report)
    assert len(_tests) == len(tr_report)
    for test_run, test in tr_report.items():
        assert 'suite_run_id' in test
        assert 'test_run_id' in test
        assert test_run == test['test_run_id']
        assert 'module' in test
        assert test['module'] == module_name
        assert 'test_configuration_options' in test
        assert [] == test['test_configuration_options']
        assert 'function' in test
        assert test['function'] in expected_result.keys()
        expected_test_result = expected_result[test['function']]
        expected_status = res.util_status_to_testrail_status(expected_test_result['status'])
        assert 'last_status' in test
        assert expected_status == test['last_status']

        # a test message will be either in 'message' or 'type' if 'message' is None
        assert 'asserts' in test
        assert type([]) == type(test['asserts'])

        # currently Tiden generates only one assert per test
        assert len(test['asserts']) == 1
        assert type({}) == type(test['asserts'][0])
        assert 'status' in test['asserts'][0]
        assert expected_status == test['asserts'][0]['status']

        expected_assert_message = expected_test_result['message'] if expected_test_result['message'] is not None else \
        expected_test_result['type']
        if expected_assert_message is not None:
            assert res.util_filter_escape_seqs(expected_assert_message) in test['asserts'][0]['message']

    # check all test run id's are unique
    test_run_ids = [test['test_run_id'] for test in tr_report.values()]
    assert len(test_run_ids) == len(set(test_run_ids))

    # check all suite run id is the same
    suite_run_ids = set([test['suite_run_id'] for test in tr_report.values()])
    assert 1 == len(suite_run_ids)


def test_runner_handle_exception_in_module_setup(with_dec_classpath, local_config, tmpdir, mock_pm):
    """
    Check that if we got exception in the module setup no one test executed.
    :return:
    """
    import pytest
    var_dir = _ensure_var_dir(tmpdir)
    xunit_file = _ensure_xunit_file_empty(var_dir)
    suite_var_dir = str(var_dir.mkdir('suite-mock'))
    config_path = str(var_dir.join('config.yaml'))

    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        'suite_var_dir': suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': suite_var_dir,
        },
        'config_path': config_path,
    })

    ssh_pool = LocalPool(local_config['ssh'])
    modules = {
        'mock3.mock_test_module_with_exceptions_in_setup': {
            'path': '%s/mock3/mock_test_module_with_exceptions_in_setup.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module_with_exceptions_in_setup',
        }
    }

    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    with pytest.raises(SystemExit):
        tr.process_tests()
    res = tr.get_tests_results()
    _tests = res.get_tests()
    print(_tests)
    assert len(_tests) == 0
    for status in res.statuses:
        assert res.get_tests_num(status) == 0


def test_runner_handle_general_exception_in_module_setup(with_dec_classpath, local_config, tmpdir, mock_pm):
    """
    Check that if we got exception in the module setup no one test executed.
    :return:
    """
    import pytest
    var_dir = _ensure_var_dir(tmpdir)
    xunit_file = _ensure_xunit_file_empty(var_dir)
    suite_var_dir = str(var_dir.mkdir('suite-mock'))
    config_path = str(var_dir.join('config.yaml'))

    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        'suite_var_dir': suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': suite_var_dir,
        },
        'config_path': config_path,
    })

    ssh_pool = LocalPool(local_config['ssh'])
    modules = {
        'mock3.mock_test_module_with_exceptions_in_setup': {
            'path': '%s/mock3/mock_test_module_with_exceptions_in_setup.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module_with_general_exceptions_in_setup',
        }
    }

    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    with pytest.raises(SystemExit):
        tr.process_tests()
    res = tr.get_tests_results()
    _tests = res.get_tests()
    print(_tests)
    assert len(_tests) == 0
    for status in res.statuses:
        assert res.get_tests_num(status) == 0


def test_runner_handle_exceptions_in_module_teardown(with_dec_classpath, local_config, tmpdir, mock_pm):
    """
    Check that if we got exception in the module teardown tests will not be failed.
    :return:
    """
    var_dir = _ensure_var_dir(tmpdir)
    xunit_file = _ensure_xunit_file_empty(var_dir)
    suite_var_dir = str(var_dir.mkdir('suite-mock'))
    config_path = str(var_dir.join('config.yaml'))

    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        'suite_var_dir': suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': suite_var_dir,
        },
        'config_path': config_path,
    })

    ssh_pool = LocalPool(local_config['ssh'])

    for class_name in ['mock_test_module_with_generic_exceptions_in_teardown',
                       'mock_test_module_with_tiden_exceptions_in_teardown']:
        modules = {
            'mock3.mock_test_module_with_exceptions_in_teardown': {
                'path': '%s/mock3/mock_test_module_with_exceptions_in_teardown.py' % config['suite_dir'],
                'module_short_name': class_name,
            }
        }

        tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
        tr.process_tests()
        res = tr.get_tests_results()
        _tests = res.get_tests()
        print(_tests)
        assert len(_tests) == 2
        assert res.get_tests_num('pass') == 2


def test_runner_repeated_decorator(with_dec_classpath, local_config, tmpdir, mock_pm):
    """
    This test is for repeated_test decorator. Checks that reporting and execution correspond to repeated_test decorator
    logic:
    1. Test executes as many times as mentioned in decorator or if it fails execution stops.
    2. If test passed during all it's iterations it marks as pass and shows as one test in results.
    3. Test uses it's unique remote directory (this is the decorator logic).
    4. If test fails in some iteration it shows as one failed test in test results and it's name changed to one that
    contains iteration maker (ex. test_one -> test_one_iteration_5).
    :return:
    """
    var_dir = _ensure_var_dir(tmpdir)
    xunit_file = _ensure_xunit_file_empty(var_dir)
    suite_var_dir = str(var_dir.mkdir('suite-mock'))
    config_path = str(var_dir.join('config.yaml'))

    module_name = 'suites.mock3.mock_test_module_with_decorators.MockTestModuleWithDecorators'
    test_prefix = module_name + '.'

    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        'suite_var_dir': suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': suite_var_dir,
        },
        'config_path': config_path,
    })

    ssh_pool = LocalPool(local_config['ssh'])
    modules = {
        'mock3.mock_test_module_with_decorators': {
            'path': '%s/mock3/mock_test_module_with_decorators.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module_with_decorators',
        }
    }
    expected_result = {
        'test_not_repeated_test': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': ['test_not_repeated_test'],
        },
        'test_repeated_test': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': ['test_repeated_test_1',
                            'test_repeated_test_2'],
        },
        'test_with_repeated_test_and_full_test_names': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': ['test_with_repeated_test_and_full_test_names_first',
                            'test_with_repeated_test_and_full_test_names_second'],
        },
        'test_with_repeated_test_and_not_full_test_names': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': ['test_with_repeated_test_and_not_full_test_names_example',
                            'test_with_repeated_test_and_not_full_test_names_2'],
        },
        'test_with_repeated_test_and_fail_on_iteration_3_iteration_3': {
            'status': 'fail',
            'type': 'TidenException',
            'message': 'TidenException(\'Exception on iteration 3\')',
            'test_name': 'test_with_repeated_test_and_fail_on_iteration_3',
            'remote_dirs': ['test_with_repeated_test_and_fail_on_iteration_3_first',
                            'test_with_repeated_test_and_fail_on_iteration_3_second',
                            'test_with_repeated_test_and_fail_on_iteration_3_3'],
        },
    }

    expected_statuses_count = {'pass': len(expected_result) - 1,
                               'fail': 1,
                               'error': 0,
                               'skip': 0,
                               'total': len(expected_result)}

    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    tr.process_tests()
    res = tr.get_tests_results()
    _tests = res.get_tests()
    print(_tests)

    # to test tests execution we check:
    # 1. correct result in the Results.
    # 2. to test correct test execution we check correct directory creation + correct logs files generation.
    assert len(_tests) == len(expected_result)

    for test_to_check in expected_result.keys():
        status, error_type, message, test_name = res.get_test_details('{}{}'.format(test_prefix, test_to_check))
        assert expected_result[test_to_check].get('status') == status
        assert expected_result[test_to_check].get('type') == error_type
        assert expected_result[test_to_check].get('message') == message \
               or expected_result[test_to_check].get('message') in message
        assert test_name is not None
        assert test_name in expected_result[test_to_check].get('test_name', test_to_check)

        # Also check directory and log file exist
        iteration = 0
        for remote_directory in expected_result[test_to_check].get('remote_dirs'):
            iteration += 1
            # test_name = expected_result[test_to_check].get('test_name', test_to_check)
            log_file = '{}/{}/{}/{}_iteration_{}.log'.format(config['rt']['remote']['test_module_dir'],
                                                             config['rt']['test_class'], remote_directory, test_name,
                                                             iteration)
            assert exists(log_file)

    for status, count in expected_statuses_count.items():
        assert res.get_tests_num(status) == count


def test_runner_repeated_test_option_all(with_dec_classpath, local_config, tmpdir, mock_pm):
    """
    This test is for testing test option repeated_test. It should have higher priority than decorator.
    If it passed through test options (like this: -to=repeated_test=10) then all tests that match suite and attributes
    will be repeated 10 times or less if some failed.
    :return:
    """
    var_dir = _ensure_var_dir(tmpdir)
    xunit_file = _ensure_xunit_file_empty(var_dir)
    suite_var_dir = str(var_dir.mkdir('suite-mock'))
    config_path = str(var_dir.join('config.yaml'))

    test_prefix = 'suites.mock3.mock_test_module_with_decorators.MockTestModuleWithDecorators.'
    iterations = 3
    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        'suite_var_dir': suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': suite_var_dir,
        },
        'config_path': str(config_path),
        'repeated_test': iterations
    })

    ssh_pool = LocalPool(local_config['ssh'])
    modules = {
        'mock3.mock_test_module_with_decorators': {
            'path': '%s/mock3/mock_test_module_with_decorators.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module_with_decorators',
        }
    }
    expected_result = {
        'test_not_repeated_test': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': [
                'test_not_repeated_test_1',
                'test_not_repeated_test_2',
                'test_not_repeated_test_3',
            ],
        },
        'test_repeated_test': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': [
                'test_repeated_test_1',
                'test_repeated_test_2',
                'test_repeated_test_3',
            ],
        },
        'test_with_repeated_test_and_full_test_names': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': [
                'test_with_repeated_test_and_full_test_names_first',
                'test_with_repeated_test_and_full_test_names_second',
                'test_with_repeated_test_and_full_test_names_3',
            ],
        },
        'test_with_repeated_test_and_not_full_test_names': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': [
                'test_with_repeated_test_and_not_full_test_names_example',
                'test_with_repeated_test_and_not_full_test_names_2',
                'test_with_repeated_test_and_not_full_test_names_3',
            ],
        },
        'test_with_repeated_test_and_fail_on_iteration_3_iteration_3': {
            'status': 'fail',
            'type': 'TidenException',
            'message': 'TidenException(\'Exception on iteration 3\')',
            'test_name': 'test_with_repeated_test_and_fail_on_iteration_3',
            'remote_dirs': ['test_with_repeated_test_and_fail_on_iteration_3_first',
                            'test_with_repeated_test_and_fail_on_iteration_3_second',
                            'test_with_repeated_test_and_fail_on_iteration_3_3'],
        },
    }

    expected_statuses_count = {'pass': len(expected_result) - 1,
                               'fail': 1,
                               'error': 0,
                               'skip': 0,
                               'total': len(expected_result)}

    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    tr.process_tests()
    res = tr.get_tests_results()
    _tests = res.get_tests()
    print(_tests)

    # to test tests execution we check:
    # 1. correct result in the Results.
    # 2. to test correct test execution we check correct directory creation + correct logs files generation.
    assert len(_tests) == len(expected_result)

    for test_to_check in expected_result.keys():
        status, error_type, message, test_name = res.get_test_details('{}{}'.format(test_prefix, test_to_check))
        assert expected_result[test_to_check].get('status') == status
        assert expected_result[test_to_check].get('type') == error_type
        assert expected_result[test_to_check].get('message') == message \
               or expected_result[test_to_check].get('message') in message
        assert test_name is not None
        assert test_name in expected_result[test_to_check].get('test_name', test_to_check)

        # Also check directory and log file exist
        iteration = 0
        for remote_directory in expected_result[test_to_check].get('remote_dirs'):
            iteration += 1
            log_file = '{}/{}/{}/{}_iteration_{}.log'.format(config['rt']['remote']['test_module_dir'],
                                                             config['rt']['test_class'], remote_directory,
                                                             test_name, iteration)
            assert exists(log_file)

    for status, count in expected_statuses_count.items():
        assert res.get_tests_num(status) == count


def test_runner_repeated_test_option_particular_test(with_dec_classpath, local_config, tmpdir, mock_pm):
    """
    This test is for testing test option repeated_test for particular test. It should have higher priority than
    decorator.
    If it passed through test options (like this: -to=repeated_test.test_name=10) then test with test_name if it matches
     suite and attributes will be repeated 10 times or less if failed.
    Other tests from suite will be repeated once or if some decorated with @repeated_test decorator - proper decorator
    logic.
    :return:
    """
    var_dir = _ensure_var_dir(tmpdir)
    xunit_file = _ensure_xunit_file_empty(var_dir)
    suite_var_dir = str(var_dir.mkdir('suite-mock'))
    config_path = str(var_dir.join('config.yaml'))
    test_prefix = 'suites.mock3.mock_test_module_with_decorators.MockTestModuleWithDecorators.'
    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        'suite_var_dir': suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': suite_var_dir,
        },
        'config_path': str(config_path),
        'repeated_test': {
            'test_not_repeated_test': 2,
            'test_repeated_test': 1,
            'test_with_repeated_test_and_full_test_names': 0,
            'test_with_repeated_test_and_fail_on_iteration_3': 2,
        }
    })

    ssh_pool = LocalPool(local_config['ssh'])
    modules = {
        'mock3.mock_test_module_with_decorators': {
            'path': '%s/mock3/mock_test_module_with_decorators.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module_with_decorators',
        }
    }
    expected_result = {
        'test_not_repeated_test': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': [
                'test_not_repeated_test_1',
                'test_not_repeated_test_2',
            ],
        },
        'test_repeated_test': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': [
                'test_repeated_test',
            ],
        },
        'test_with_repeated_test_and_full_test_names': {
            'status': 'skipped',
            'type': 'skipped due to repeated_test iterations <= 0',
            'message': None,
            'remote_dirs': [],
        },
        'test_with_repeated_test_and_not_full_test_names': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': ['test_with_repeated_test_and_not_full_test_names_example',
                            'test_with_repeated_test_and_not_full_test_names_2'],
        },
        'test_with_repeated_test_and_fail_on_iteration_3': {
            'status': 'pass',
            'type': None,
            'test_name': 'test_with_repeated_test_and_fail_on_iteration_3_iteration_3',
            'message': None,
            'remote_dirs': ['test_with_repeated_test_and_fail_on_iteration_3_first',
                            'test_with_repeated_test_and_fail_on_iteration_3_second'],
        },
    }

    expected_statuses_count = {'pass': len(expected_result) - 1,
                               'fail': 0,
                               'error': 0,
                               'skip': 1,
                               'total': len(expected_result)}

    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    tr.process_tests()
    res = tr.get_tests_results()
    _tests = res.get_tests()
    print(_tests)

    # to test tests execution we check:
    # 1. correct result in the Results.
    # 2. to test correct test execution we check correct directory creation + correct logs files generation.
    assert len(_tests) == len(expected_result)

    for test_to_check in expected_result.keys():
        status, error_type, message, test_name = res.get_test_details('{}{}'.format(test_prefix, test_to_check))
        assert expected_result[test_to_check].get('status') == status
        assert expected_result[test_to_check].get('type') == error_type
        assert expected_result[test_to_check].get('message') == message \
               or expected_result[test_to_check].get('message') in message
        assert test_name is not None
        assert test_name in expected_result[test_to_check].get('test_name', test_to_check)

        # Also check directory and log file exist
        iteration = 0
        for remote_directory in expected_result[test_to_check].get('remote_dirs'):
            iteration += 1
            log_file = '{}/{}/{}/{}_iteration_{}.log'.format(config['rt']['remote']['test_module_dir'],
                                                             config['rt']['test_class'], remote_directory, test_name,
                                                             iteration)
            assert exists(log_file)

    for status, count in expected_statuses_count.items():
        assert res.get_tests_num(status) == count


def test_runner_repeated_test_continue_on_fail(with_dec_classpath, local_config, tmpdir, mock_pm):
    """
    This test is for testing test option repeated_test_continue_on_fail. It should have higher priority than decorator.
    If it passed through test options (like this: -to=repeated_test_continue_on_fail=True) then test with repeated test
    decorators will be executed even if some iteration will be failed.
    :return:
    """
    var_dir = _ensure_var_dir(tmpdir)
    xunit_file = _ensure_xunit_file_empty(var_dir)
    suite_var_dir = str(var_dir.mkdir('suite-mock'))
    config_path = str(var_dir.join('config.yaml'))

    test_prefix = 'suites.mock3.mock_test_module_with_decorators.MockTestModuleWithDecorators.'
    iterations = 5
    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        'suite_var_dir': suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': suite_var_dir,
        },
        'config_path': str(config_path),
        'repeated_test': iterations,
        'repeated_test_continue_on_fail': True
    })

    ssh_pool = LocalPool(local_config['ssh'])
    modules = {
        'mock3.mock_test_module_with_decorators': {
            'path': '%s/mock3/mock_test_module_with_decorators.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module_with_decorators',
        }
    }
    expected_result = {
        'test_not_repeated_test': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': [
                'test_not_repeated_test_1',
                'test_not_repeated_test_2',
                'test_not_repeated_test_3',
                'test_not_repeated_test_4',
                'test_not_repeated_test_5',
            ],
        },
        'test_repeated_test': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': [
                'test_repeated_test_1',
                'test_repeated_test_2',
                'test_repeated_test_3',
                'test_repeated_test_4',
                'test_repeated_test_5',
            ],
        },
        'test_with_repeated_test_and_full_test_names': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': [
                'test_with_repeated_test_and_full_test_names_first',
                'test_with_repeated_test_and_full_test_names_second',
                'test_with_repeated_test_and_full_test_names_3',
                'test_with_repeated_test_and_full_test_names_4',
                'test_with_repeated_test_and_full_test_names_5',
            ],
        },
        'test_with_repeated_test_and_not_full_test_names': {
            'status': 'pass',
            'type': None,
            'message': None,
            'remote_dirs': [
                'test_with_repeated_test_and_not_full_test_names_example',
                'test_with_repeated_test_and_not_full_test_names_2',
                'test_with_repeated_test_and_not_full_test_names_3',
                'test_with_repeated_test_and_not_full_test_names_4',
                'test_with_repeated_test_and_not_full_test_names_5',
            ],
        },
        'test_with_repeated_test_and_fail_on_iteration_3': {
            'status': 'fail',
            'type': 'TidenException',
            'message': 'TidenException(\'Exception on iteration 3\')',
            'test_name': 'test_with_repeated_test_and_fail_on_iteration_3',
            'remote_dirs': ['test_with_repeated_test_and_fail_on_iteration_3_first',
                            'test_with_repeated_test_and_fail_on_iteration_3_second',
                            'test_with_repeated_test_and_fail_on_iteration_3_3',
                            'test_with_repeated_test_and_fail_on_iteration_3_4',
                            'test_with_repeated_test_and_fail_on_iteration_3_5'
                            ]
        },
    }

    expected_statuses_count = {'pass': len(expected_result) - 1,
                               'fail': 1,
                               'error': 0,
                               'skip': 0,
                               'total': len(expected_result)}

    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    tr.process_tests()
    res = tr.get_tests_results()
    _tests = res.get_tests()
    print(_tests)

    # to test tests execution we check:
    # 1. correct result in the Results.
    # 2. to test correct test execution we check correct directory creation + correct logs files generation.
    assert len(_tests) == len(expected_result)

    for test_to_check in expected_result.keys():
        status, error_type, message, test_name = res.get_test_details('{}{}'.format(test_prefix, test_to_check))
        assert expected_result[test_to_check].get('status') == status
        assert expected_result[test_to_check].get('type') == error_type
        assert expected_result[test_to_check].get('message') == message \
               or expected_result[test_to_check].get('message') in message
        assert test_name is not None
        assert test_name in expected_result[test_to_check].get('test_name', test_to_check)

        # Also check directory and log file exist
        iteration = 0
        for remote_directory in expected_result[test_to_check].get('remote_dirs'):
            iteration += 1
            log_file = '{}/{}/{}/{}_iteration_{}.log'.format(config['rt']['remote']['test_module_dir'],
                                                             config['rt']['test_class'], remote_directory,
                                                             test_name, iteration)
            assert exists(log_file)

    for status, count in expected_statuses_count.items():
        assert res.get_tests_num(status) == count


def test_runner_skipped_configurations(with_dec_classpath, local_config, tmpdir, mock_pm):
    """
    Test configurations correctly passed to TestRail report for skipped tests
    :return:
    """
    var_dir = _ensure_var_dir(tmpdir)
    xunit_file = _ensure_xunit_file_empty(var_dir)
    testrail_report_file = _ensure_tr_report_file_empty(var_dir)

    suite_var_dir = str(var_dir.mkdir('suite-mock'))
    config_path = str(var_dir.join('config.yaml'))
    source = 'mock_test_module_with_test_configuration'
    suite = 'mock'
    module_name = 'suites.%s.%s.MockTestModuleWithTestConfiguration' % (suite, source)
    test_prefix = module_name + '.'

    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        # 'attrib': 'test_runner',
        # 'attr_match': 'any',
        'suite_var_dir': suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': suite_var_dir,
        },
        'config_path': config_path,
        'zookeeper_enabled': False,
        'pitr_enabled': False,
        'compaction_enabled': True,
    })

    ssh_pool = LocalPool(local_config['ssh'])
    test_module_source_file_name = '%s/%s/%s.py' % (config['suite_dir'], suite, source)

    modules = {
        '%s.%s' % (suite, source): {
            'path': test_module_source_file_name,
            'module_short_name': source,
        }
    }
    test_configuration = '(pitr_enabled=false, compaction_enabled=true, zookeeper_enabled=false)'
    expected_configuration_options = ['pitr_enabled', 'compaction_enabled', 'zookeeper_enabled']
    expected_result = {
        'test_main':
            {'status': 'pass', 'type': None, 'message': None},
        'test_zookeeper_only':
            {'status': 'skipped', 'type': 'skipped cause of config.zookeeper_enabled is False', 'message': None},
    }

    expected_statuses_count = {'pass': 1,
                               'fail': 0,
                               'error': 0,
                               'skip': 1,
                               'total': len(expected_result)}

    from tiden.tidenfabric import TidenFabric
    TidenFabric().reset().setConfig(config)
    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    tr.process_tests()
    res = tr.get_tests_results()
    res.create_testrail_report(config, report_file=basename(testrail_report_file))
    _tests = res.get_tests()
    print(_tests)

    # validate raw test results
    assert len(_tests) == len(expected_result)

    for test_to_check in expected_result.keys():
        status, error_type, message, test_name = res.get_test_details('{}{}{}'.format(test_prefix, test_to_check, test_configuration))
        assert expected_result[test_to_check].get('status') == status
        assert expected_result[test_to_check].get('type') == error_type
        if expected_result[test_to_check].get('message') is None:
            assert message is None
        else:
            assert expected_result[test_to_check].get('message') == message \
                   or expected_result[test_to_check].get('message') in message

    for status, count in expected_statuses_count.items():
        assert res.get_tests_num(status) == count

    # validate generated TestRail .yaml report
    tr_report = read_yaml_file(testrail_report_file)
    assert type({}) == type(tr_report)
    assert len(_tests) == len(tr_report)
    for test_run, test in tr_report.items():
        assert 'suite_run_id' in test
        assert 'test_run_id' in test
        assert test_run == test['test_run_id']
        assert 'module' in test
        assert test['module'] == module_name
        assert 'test_configuration_options' in test
        assert expected_configuration_options == test['test_configuration_options']
        assert 'function' in test
        assert test['function'] in expected_result.keys()
        expected_test_result = expected_result[test['function']]
        expected_status = res.util_status_to_testrail_status(expected_test_result['status'])
        assert 'last_status' in test
        assert expected_status == test['last_status']

        # a test message will be either in 'message' or 'type' if 'message' is None
        assert 'asserts' in test
        assert type([]) == type(test['asserts'])

        # currently Tiden generates only one assert per test
        assert len(test['asserts']) == 1
        assert type({}) == type(test['asserts'][0])
        assert 'status' in test['asserts'][0]
        assert expected_status == test['asserts'][0]['status']

        expected_assert_message = expected_test_result['message'] if expected_test_result['message'] is not None else \
        expected_test_result['type']
        if expected_assert_message is not None:
            assert res.util_filter_escape_seqs(expected_assert_message) in test['asserts'][0]['message']

    # check all test run id's are unique
    test_run_ids = [test['test_run_id'] for test in tr_report.values()]
    assert len(test_run_ids) == len(set(test_run_ids))

    # check all suite run id is the same
    suite_run_ids = set([test['suite_run_id'] for test in tr_report.values()])
    assert 1 == len(suite_run_ids)


def test_runner_run_negated_required_test_when_no_option_passed(with_dec_classpath, local_config, tmpdir, mock_pm):
    """
    Test configurations correctly passed to TestRail report for skipped tests
    :return:
    """
    var_dir = _ensure_var_dir(tmpdir)
    xunit_file = _ensure_xunit_file_empty(var_dir)
    testrail_report_file = _ensure_tr_report_file_empty(var_dir)

    suite_var_dir = str(var_dir.mkdir('suite-mock'))
    config_path = str(var_dir.join('config.yaml'))
    source = 'mock_test_module_with_negated_option'
    suite = 'mock4'
    module_name = 'suites.%s.%s.MockTestModuleWithNegatedOption' % (suite, source)
    test_prefix = module_name + '.'

    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        'suite_var_dir': suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': suite_var_dir,
        },
        'config_path': config_path,
        # for that test we do NOT pass an option to test runner
        # 'zookeeper_enabled': True
    })

    ssh_pool = LocalPool(local_config['ssh'])
    test_module_source_file_name = '%s/%s/%s.py' % (config['suite_dir'], suite, source)

    modules = {
        '%s.%s' % (suite, source): {
            'path': test_module_source_file_name,
            'module_short_name': source,
        }
    }

    expected_result = {
        'test_main':
            {'status': 'pass', 'type': None, 'message': None},
        'test_without_zookeeper_only':
            {'status': 'pass', 'type': None, 'message': None},
        'test_with_zookeeper_only':
            {'status': 'skipped', 'type': 'skipped cause of config.zookeeper_enabled is None', 'message': None},
    }

    expected_statuses_count = {'pass': 2,
                               'fail': 0,
                               'error': 0,
                               'skip': 1,
                               'total': len(expected_result)}

    from tiden.tidenfabric import TidenFabric
    TidenFabric().reset().setConfig(config)
    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    tr.process_tests()
    res = tr.get_tests_results()
    res.create_testrail_report(config, report_file=basename(testrail_report_file))
    _tests = res.get_tests()
    print(_tests)

    # validate raw test results
    assert len(_tests) == len(expected_result)

    for test_to_check in expected_result.keys():
        status, error_type, message, test_name = res.get_test_details('{}{}'.format(test_prefix, test_to_check))
        assert expected_result[test_to_check].get('status') == status
        assert expected_result[test_to_check].get('type') == error_type
        if expected_result[test_to_check].get('message') is None:
            assert message is None
        else:
            assert expected_result[test_to_check].get('message') == message \
                   or expected_result[test_to_check].get('message') in message

    for status, count in expected_statuses_count.items():
        assert res.get_tests_num(status) == count

    # validate generated TestRail .yaml report
    tr_report = read_yaml_file(testrail_report_file)
    assert type({}) == type(tr_report)
    assert len(_tests) == len(tr_report)
    for test_run, test in tr_report.items():
        assert 'suite_run_id' in test
        assert 'test_run_id' in test
        assert test_run == test['test_run_id']
        assert 'module' in test
        assert test['module'] == module_name
        assert 'test_configuration_options' in test
        assert [] == test['test_configuration_options']
        assert 'function' in test
        assert test['function'] in expected_result.keys()
        expected_test_result = expected_result[test['function']]
        expected_status = res.util_status_to_testrail_status(expected_test_result['status'])
        assert 'last_status' in test
        assert expected_status == test['last_status']

        # a test message will be either in 'message' or 'type' if 'message' is None
        assert 'asserts' in test
        assert type([]) == type(test['asserts'])

        # currently Tiden generates only one assert per test
        assert len(test['asserts']) == 1
        assert type({}) == type(test['asserts'][0])
        assert 'status' in test['asserts'][0]
        assert expected_status == test['asserts'][0]['status']

        expected_assert_message = expected_test_result['message'] if expected_test_result['message'] is not None else \
        expected_test_result['type']
        if expected_assert_message is not None:
            assert res.util_filter_escape_seqs(expected_assert_message) in test['asserts'][0]['message']

    # check all test run id's are unique
    test_run_ids = [test['test_run_id'] for test in tr_report.values()]
    assert len(test_run_ids) == len(set(test_run_ids))

    # check all suite run id is the same
    suite_run_ids = set([test['suite_run_id'] for test in tr_report.values()])
    assert 1 == len(suite_run_ids)

