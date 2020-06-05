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

from .conftest import check_runtests_protocol
from os.path import join, dirname


def test_class_decorator_not_decorated_module(with_dec_classpath):
    """
    Smoke check run-tests.py protocol for non-decorated test class
    """

    check_runtests_protocol(
        module_name='suites.mock.mock_test_module',
        short_name='MockTestModule'
    )


def test_class_decorator(with_dec_classpath):
    """
    Check run-tests.py protocol for decorated test class AND check decoration correctly adds attributes.
    """

    test_class = check_runtests_protocol(
        module_name='suites.mock.mock_test_module_with_test_configuration',
        short_name='MockTestModuleWithTestConfiguration',
        _config={
            'zookeeper_enabled': True,
        }
    )

    assert hasattr(test_class, '__configuration_options__')
    configuration_options = getattr(test_class, '__configuration_options__')
    assert isinstance(configuration_options, list)
    assert 3 == len(configuration_options)

    assert hasattr(test_class, '__configurations__')
    configurations = getattr(test_class, '__configurations__')
    assert isinstance(configurations, list)
    assert 8 == len(configurations)


def test_class_decorator_with_limited_set_of_configurations(with_dec_classpath):
    """
    Check another variant of decoration: not only configuration options specified, but also a set of configurations
    """

    test_class = check_runtests_protocol(
        module_name='suites.mock.mock_test_module_with_test_configuration_subset',
        short_name='MockTestModuleWithTestConfigurationSubset'
    )

    assert hasattr(test_class, '__configuration_options__')
    configuration_options = getattr(test_class, '__configuration_options__')
    assert isinstance(configuration_options, list)
    assert 4 == len(configuration_options)

    assert hasattr(test_class, '__configurations__')
    configurations = getattr(test_class, '__configurations__')
    assert isinstance(configurations, list)
    assert 4 == len(configurations)


def test_class_decorator_collect_tests(with_dec_classpath, tmpdir):
    from tiden.result import Result

    var_dir = str(tmpdir.mkdir('var'))
    suite_var_dir = str(tmpdir.join('var').mkdir('suite-mock'))
    xunit_file = str(tmpdir.join('var').join('xunit.xml'))
    tmpdir.join('var').join('xunit.xml').write('', ensure=True)
    report_path = 'report.yaml'

    res = Result(xunit_path=xunit_file)
    config = {
        'artifacts': {},
        'suite_var_dir': suite_var_dir,
        'suite_name': 'mock',
        'test_name': '*',
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': '',
        }
    }
    modules = {
        'mock.mock_test_module': {
            'path': '%s/mock/mock_test_module.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module',
        },
        'mock.mock_test_module_with_test_configuration': {
            'path': '%s/mock/mock_test_module_with_test_configuration.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module_with_test_configuration',
        },
        'mock.mock_test_module_with_test_configuration_subset': {
            'path': '%s/mock/mock_test_module_with_test_configuration_subset.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module_with_test_configuration_subset',
        },
    }
    from tiden.tidenrunner import TidenRunner
    tr = TidenRunner(config, modules=modules, xunit_path=xunit_file, collect_only=True)
    tr.collect_tests()
    res = tr.get_tests_results()
    res.flush_xunit()
    res.create_testrail_report(config, report_file=str(report_path))


def test_class_decorator_process_tests(with_dec_classpath, local_config, tmpdir, mock_pm):
    from tiden.result import Result
    from tiden.localpool import LocalPool
    from tiden.util import cfg
    from copy import deepcopy

    var_dir = str(tmpdir.mkdir('var'))
    suite_var_dir = str(tmpdir.join('var').mkdir('suite-mock'))
    xunit_file = str(tmpdir.join('var').join('xunit.xml'))
    tmpdir.join('var').join('xunit.xml').write('', ensure=True)
    config_path = tmpdir.join('var').join('config.yaml')
    report_path = 'report.yaml'

    config = deepcopy(local_config)

    config.update({
        'artifacts': {},
        'suite_var_dir': suite_var_dir,
        'suite_name': 'mock',
        'test_name': '*',
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': '',
        },
        'config_path': str(config_path),
    })
    cfg(config, 'pitr_enabled', 'True')
    cfg(config, 'load_factor', '0.1')

    ssh_pool = LocalPool(local_config['ssh'])
    res = Result(xunit_path=xunit_file)
    modules = {
        'mock.mock_test_module': {
            'path': '%s/mock/mock_test_module.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module',
        },
        'mock.mock_test_module_with_test_configuration': {
            'path': '%s/mock/mock_test_module_with_test_configuration.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module_with_test_configuration',
        },
        'mock.mock_test_module_with_test_configuration_subset': {
            'path': '%s/mock/mock_test_module_with_test_configuration_subset.py' % config['suite_dir'],
            'module_short_name': 'mock_test_module_with_test_configuration_subset',
        },
    }
    from tiden.tidenrunner import TidenRunner
    ssh_pool.connect()
    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    tr.process_tests()
    res = tr.get_tests_results()
    res.flush_xunit()
    res.create_testrail_report(config, report_file=str(report_path))

