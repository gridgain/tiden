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


def test_priority_decorator_not_decorated_module(with_dec_classpath):
    """
    Smoke check run-tests.py protocol for non-decorated test class
    """

    test_class = check_runtests_protocol(
        module_name='suites.mock2.mock_test_module',
        short_name='MockTestModule'
    )

    test_method = getattr(test_class, 'test_simple')
    assert not hasattr(test_method, '__priority__')


def test_priority_decorator_decorated_module(with_dec_classpath):
    """
    Smoke check run-tests.py protocol for non-decorated test class
    """

    test_class = check_runtests_protocol(
        module_name='suites.mock2.mock_test_module_with_test_priorities',
        short_name='MockTestModuleWithTestPriorities'
    )
    for test_method_name in dir(test_class):
        if test_method_name.startswith('test_'):
            test_method = getattr(test_class, test_method_name)
            if test_method_name not in ['test_main']:
                assert hasattr(test_method, '__priority__')
            else:
                assert not hasattr(test_method, '__priority__')


def test_priority_decorator_run_tests(with_dec_classpath, local_config, tmpdir, mock_pm):
    from tiden.result import Result
    from tiden.localpool import LocalPool
    from copy import deepcopy

    var_dir = str(tmpdir.mkdir('var'))
    suite_var_dir = str(tmpdir.join('var').mkdir('suite-mock2'))
    remote_suite_var_dir = str(tmpdir.join('var').mkdir('remote').mkdir('suite-mock2'))
    xunit_file = str(tmpdir.join('var').join('xunit.xml'))
    tmpdir.join('var').join('xunit.xml').write('', ensure=True)

    res = Result(xunit_path=xunit_file)
    config = deepcopy(local_config)
    config.update({
        'suite_var_dir': suite_var_dir,
        'suite_name': 'mock2',
        'test_name': '*',
        'config_path': '%s/config.yaml' % suite_var_dir,
        'suite_dir': join(dirname(__file__), 'res', 'decorators', 'suites'),
        'remote': {
            'suite_var_dir': remote_suite_var_dir,
        }
    })
    ssh_pool = LocalPool(local_config['ssh'])
    modules = {
        'mock2.mock_test_module_with_test_priorities': {
            'path': join(config['suite_dir'], 'mock2', 'mock_test_module_with_test_priorities.py'),
            'module_short_name': 'mock_test_module_with_test_priorities',
        },
    }
    from tiden.tidenrunner import TidenRunner
    tr = TidenRunner(config, modules=modules, ssh_pool=ssh_pool, plugin_manager=mock_pm, xunit_path=xunit_file)
    tr.process_tests()

