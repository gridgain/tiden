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

from .tidenpluginmanager import PluginManager

from .report.steps import step, InnerReportConfig, Step, add_attachment, AttachmentType
from .util import log_print, unix_path, call_method, create_case, kill_stalled_java, exec_time
from .result import Result
from .util import write_yaml_file, should_be_skipped
from .logger import *
from .runner import get_test_modules, get_long_path_len, get_class_from_module, known_issue_str
from .priority_decorator import get_priority_key
from .sshpool import SshPool
from uuid import uuid4
from traceback import format_exc

from .runner import set_configuration_options, get_configuration_representation, get_actual_configuration

from importlib import import_module
from os import path, mkdir
from time import time
from shutil import copyfile
from os.path import join, basename
from glob import glob
import traceback


class TidenTestPlan:
    all_tests = None
    skipped_tests = None
    tests_to_execute = None

    def __init__(self):
        self.all_tests = {}
        self.skipped_tests = []
        self.tests_to_execute = []

    def update(self, other):
        self.all_tests.update(other.all_tests)
        self.skipped_tests.extend(other.skipped_tests)
        self.tests_to_execute.extend(other.tests_to_execute)


class TidenRunner:
    # {
    #   '<suite_name>.<test_file_name>': {
    #       'path': <full-path-to-test-file>,
    #       'module_short_name': <test_file_name>,
    #   }
    # }
    modules = None

    # Tiden config dictionary
    config = None

    # Tiden SshPool instance
    ssh_pool = None

    # Tiden PluginManager instance
    pm = None

    # longest length of the test name
    long_path_len = 0

    # instance of Result class
    result = None

    # current test module, a key to self.modules dictionary
    test_module = None

    # == TidenTestPlan for all modules:

    total = None

    # dictionary of TidenTestPlan indexed by test module name
    test_plan = {}

    # == for current test module:

    # a short name of test module, e.g. test module file name without .py extension
    module_short_name = None

    # a name of module' test class
    test_class_name = None

    # instance of current module' test case class
    test_class = None

    # == for current test within module:

    # test name, with all configuration options
    current_test_name = None

    # test method name only
    current_test_method = None

    def __init__(self, config, **kwargs):
        if kwargs.get('modules', None) is not None:
            self.modules = kwargs.get('modules')
        else:
            self.modules = get_test_modules(config, collect_only=kwargs.get('collect_only'))
        self.config = config
        self.long_path_len = get_long_path_len(self.modules)

        xunit_path_var = None
        if kwargs.get('xunit_path'):
            xunit_path_var = kwargs.get('xunit_path')
        elif config.get('var_dir') and config.get('xunit_file'):
            xunit_path_var = join(config.get('var_dir'), config.get('xunit_file'))
        self.result = Result(xunit_path=xunit_path_var)

        self.ssh_pool: SshPool = kwargs.get('ssh_pool')
        self.pm: PluginManager = kwargs.get('plugin_manager')

    def collect_tests(self):
        """
        Collect tests from all modules.
        """
        log_print("*** Collecting tests ***", color='blue')
        long_path_len = get_long_path_len(self.modules)

        from tiden.sshpool import AbstractSshPool
        self.ssh_pool = AbstractSshPool({'hosts': []})

        def empty_init(self, config, ssh_pool):
            self.config = config
            self.ssh = ssh_pool

        self.__prepare_session_vars()

        for test_module in sorted(self.modules.keys()):
            # cleanup instance vars
            self.test_plan[test_module] = TidenTestPlan()

            self.__prepare_module_vars(test_module, fake_init=empty_init)
            self.__print_current_module_name()

            test_method_names = sorted(list(self.gen_tests(self.test_class)))

            self.create_test_module_attr_yaml(test_method_names)
            self.collect_tests0(test_method_names)

            self.total.update(self.test_plan[test_module])

        log_print("*** Found %s tests. %s skipped. Going to 'run' %s tests ***" % (
            len(self.total.all_tests),
            len(self.total.skipped_tests),
            len(self.total.tests_to_execute)
        ), color='blue')

        test_cnt = 0

        # Skipped tests do not hit collect report
        # Now generate results for 'executed' tests
        for test_module in sorted(self.modules.keys()):
            self.__prepare_module_vars(test_module, fake_init=empty_init)
            test_plan = self.test_plan[self.test_module]

            for test_name in sorted(test_plan.tests_to_execute):
                test_param = test_plan.all_tests[test_name]
                self.__prepare_test_vars(**test_param)

                test_cnt = test_cnt + 1
                self.result.start_testcase(self.test_class, self.current_test_name)
                self.__print_found_test_method_to_execute(long_path_len, test_cnt, test_module)
                self.result.stop_testcase('pass')

    def process_tests(self):
        """
        Run all tests
        :return:
        """
        log_print("*** Tests ***", color='blue')

        self.__prepare_session_vars()

        # Check requirements for applications
        for test_module in sorted(self.modules.keys()):
            module = import_module("suites.%s" % test_module)
            test_class_name = get_class_from_module(self.modules[test_module]['module_short_name'])
            test_class = getattr(module, test_class_name)(self.config, self.ssh_pool)
            if hasattr(test_class, 'check_requirements'):
                test_class.check_requirements()

        for test_module in sorted(self.modules.keys()):
            # cleanup instance vars
            self.test_plan[test_module] = TidenTestPlan()

            self.__prepare_module_vars(test_module)

            # find test methods:
            if hasattr(self.test_class, '__configurations__'):
                cfg_options = getattr(self.test_class, '__configuration_options__')
                configuration = get_actual_configuration(self.config, cfg_options)

                log_print("Configuration options for %s:\n%s" % (self.test_class.__class__.__name__,
                                                                 '\n'.join([
                                                                     '\t' + cfg_option_name + '=' + str(
                                                                         configuration[i])
                                                                     for i, cfg_option_name in enumerate(cfg_options)
                                                                 ])),
                          color='blue')
            else:
                cfg_options = None
                configuration = None

            test_method_names = list(self.gen_tests(self.test_class))

            self.collect_tests1(test_method_names, common_test_param={
                'configuration': configuration,
                'cfg_options': cfg_options,
            })

            test_plan = self.test_plan[self.test_module]
            if len(test_plan.skipped_tests) > 0:
                self._skip_tests()

            if len(test_plan.tests_to_execute) > 0:
                tests_to_execute = sorted(test_plan.tests_to_execute, key=get_priority_key(self.test_class))

                log_print("*** Found %s tests in %s. %s skipped. Going to run %s tests ***\n%s" % (
                    len(test_plan.all_tests), self.test_class_name, len(test_plan.skipped_tests),
                    len(test_plan.tests_to_execute),
                    '\n'.join([
                        test_plan.all_tests[test_name]['test_method_name']
                        for test_name in tests_to_execute
                    ])),
                          color='blue')

                # Execute module setup
                setup_passed = self.__call_module_setup_teardown('setup')

                if setup_passed:
                    self._run_tests(tests_to_execute)

                # Execute module teardown
                self.__call_module_setup_teardown('teardown')

                # this is for correct fail in Jenkins
                if not setup_passed:
                    exit(1)

    def create_test_module_attr_yaml(self, test_method_names):
        # create attr.yaml
        for current_test_name in test_method_names:
            test_function = getattr(self.test_class, current_test_name)
            create_case(test_function)

    def __prepare_session_vars(self):
        self.test_plan = {}
        self.total = TidenTestPlan()

    def __prepare_module_vars(self, module_name, fake_init=None):
        """
        Prepare per-module initialization of internal variables:

        Expects self.test_module be set to proper full name of module under 'suites' directory

        sets up
            self.test_class_name
            self.module_short_name
            self.test_class - creates instance of test case class
        resets
            self.all_tests, self.tests_to_execute, self.skipped_tests
        config
            fills in config['rt'], config['rt']['remote']

        Creates test module working local and remote directories.

        Copies resources from suite directory to local test module working directory.

        :param module_name: name of the module to prepare
        :param fake_init: do not init module
        :return:
        """
        self.test_module = module_name

        # fill new module vars
        self.module_short_name = self.modules[self.test_module]['module_short_name']
        test_module_dir = "%s/%s" % (self.config['suite_var_dir'], self.module_short_name)
        remote_test_module_dir = "%s/%s" % (self.config['remote']['suite_var_dir'], self.module_short_name)

        self.test_class_name = get_class_from_module(self.module_short_name)

        # Update Tiden config
        self.config['rt'] = {
            'test_class': self.test_class_name,
            'test_method': None,
            'test_module': self.test_module,
            'test_module_name': self.module_short_name,
            'test_module_dir': test_module_dir,
            'remote': {
                'test_module_dir': remote_test_module_dir,
            }
        }

        module = import_module("suites.%s" % self.test_module)

        # used for collect_only
        if fake_init:
            self.test_class = getattr(module, self.test_class_name)
            self.test_class.__init__ = fake_init
            self.test_class = getattr(module, self.test_class_name)(self.config, self.ssh_pool)
        else:
            # for process tests - prepare test directory and resources
            self.__create_test_module_directory(remote_test_module_dir, test_module_dir)

            self.test_class = getattr(module, self.test_class_name)(self.config, self.ssh_pool)

            if hasattr(self.test_class, 'tiden'):
                self.__copy_resources_to_local_test_module_directory()

                # Set ssh and config apps model classes
                self.test_class.tiden.config = self.config
                self.test_class.tiden.ssh = self.ssh_pool

            self.test_class.config = self.config
            self.test_class.ssh = self.ssh_pool

            self._save_config()

    def __prepare_test_vars(self, test_method_name=None, configuration=None, cfg_options=None, **kwargs):
        if not test_method_name:
            return
        self.test_iteration = 1
        self.current_test_method = test_method_name

        if hasattr(self.test_class, '__configurations__'):
            if cfg_options is None:
                cfg_options = getattr(self.test_class, '__configuration_options__')
            if configuration is None:
                configuration = get_actual_configuration(self.config, cfg_options)
            configuration_representation = get_configuration_representation(cfg_options, configuration)
            self.current_test_name = self.current_test_method + configuration_representation
        else:
            self.current_test_name = self.current_test_method

    def collect_test0(self):
        # collect test params
        test_params = {
            'test_name': self.current_test_name,
        }
        test_function = getattr(self.test_class, self.current_test_method)
        # first setup fixture
        if hasattr(test_function, "__setup__"):
            setup_fixture = getattr(test_function, "__setup__")
            if type(setup_fixture) == type(''):
                setup_method = getattr(self.test_class, setup_fixture)
            else:
                setup_method = setup_fixture
                test_params['setup_test_params'] = True

            test_params['setup_test_method'] = setup_method

        # next, teardown fixture
        if hasattr(test_function, "__teardown__"):
            teardown_fixture = getattr(test_function, "__teardown__")
            teardown_method = getattr(self.test_class, teardown_fixture)
            test_params['teardown_test_method'] = teardown_method

        # don't forget known issues
        if hasattr(test_function, "__known_issues__"):
            known_issue = getattr(test_function, "__known_issues__")
            test_params['known_issue'] = known_issue

        # test by default runs only once,
        # unless repeated_test_count set explicitly by decorator or framework option
        repeat_count = 1
        # here, we check --to=repeated_test=N and --to=repeated_test.test_name=N options
        # and decorate test with @repeated_test automagically if that's required
        if self.config.get('repeated_test'):
            repeated_test_option = self.config['repeated_test']
            re_decorate = False
            if type({}) != type(repeated_test_option):
                # if option was given as --to=repeated_test=N, re-decorate all tests
                re_decorate = True
                repeat_count = int(repeated_test_option)
            elif self.current_test_method in repeated_test_option.keys():
                # otherwise re-decorate only if test name matches given option
                re_decorate = True
                repeat_count = int(repeated_test_option[self.current_test_method])

            if re_decorate:
                from tiden.util import repeated_test
                original_test = test_function
                if hasattr(original_test, 'repeated_test_name'):
                    # that test was previously decorated by @repeated_test, extract original test_names
                    original_names = original_test.repeated_test_name
                    decorated_test = repeated_test(repeat_count,
                                                   test_names=original_names)(original_test.__func__)
                else:
                    # that's a brand new decoration
                    decorated_test = repeated_test(repeat_count)(original_test.__func__)

                # this magic required to convert decorated test function to method of a test class
                from types import MethodType
                setattr(self.test_class, self.current_test_method, MethodType(decorated_test, self.test_class))
                test_function = getattr(self.test_class, self.current_test_method)

        if hasattr(test_function, 'repeated_test_count'):
            repeat_count = test_function.repeated_test_count

            repeated_test_name = test_function.repeated_test_name
            test_params['repeated_test_count'] = repeat_count
            test_params['repeated_test_name'] = repeated_test_name
            test_params['continue_on_fail'] = self.config.get('repeated_test_continue_on_fail', False)
        return test_params

    def _skip_tests(self):
        test_plan = self.test_plan[self.test_module]
        skipped_tests = sorted(test_plan.skipped_tests)
        try:
            for current_test in skipped_tests:
                test_param = test_plan.all_tests[current_test]
                self.__prepare_test_vars(**test_param)
                pad_string = self.__get_pad_string(msg=self.current_test_method)

                self.result.skip_testcase_no_start(self.test_class, self.current_test_name,
                                                   skip_message=test_param['skip_msg'],
                                                   skip_no_start=test_param['skip_no_start'])
                self.result.update_xunit()
                log_print("%s %s" % (pad_string, test_param['skip_msg']), color='yellow')
        finally:
            self.current_test_name = None
            self.current_test_method = None

    def _run_tests(self, tests_to_execute):
        test_plan = self.test_plan[self.test_module]

        try:
            for test_cnt, current_test in enumerate(tests_to_execute, start=1):
                test_param = test_plan.all_tests[current_test]
                self.__prepare_test_vars(**test_param)

                repeated_test_count = test_param.get('repeated_test_count', 1)
                repeated_test_continue_on_fail = test_param.get('continue_on_fail')
                test_with_iterations = True if repeated_test_count > 1 else False
                pad_string = self.__get_pad_string()
                log_print("%s started (%s from %s)" % (pad_string, test_cnt, len(tests_to_execute)), color='yellow')

                for self.test_iteration in range(repeated_test_count):
                    if test_with_iterations:
                        log_print("{} started (iteration {} from {})".format(pad_string,
                                                                             self.test_iteration + 1,
                                                                             repeated_test_count), color='yellow')

                    test_status = self._run_test()

                    if test_with_iterations and test_status != 'pass' and not repeated_test_continue_on_fail:
                        self.result.update_test_name('{}_iteration_{}'.format(current_test, self.test_iteration + 1))
                        break
        finally:
            self.current_test_name = None
            self.current_test_method = None

    def _run_test(self):
        setattr(self, '_secret_report_storage', InnerReportConfig())
        test_exception = None
        tb_msg = None
        test_status = 'pass'
        pad_string = self.__get_pad_string()
        started = int(time())
        known_issue = self.test_plan[self.test_module].all_tests[self.current_test_name].get('known_issue')
        setattr(self.test_class, '_secret_report_storage', InnerReportConfig())
        try:
            self.pm.do("before_test_method",
                       test_module=self.test_module,
                       test_name=self.current_test_name,
                       artifacts=self.config.get('artifacts', {}))
            self.result.start_testcase(self.test_class, self.current_test_name)
            self.__update_config_and_save(current_method_name=self.current_test_name)

            # Execute test setup method
            self.__call_test_setup_teardown('setup')

            # self.__print_with_format()

            with Step(self, 'Execution'):
                try:
                    call_method(self.test_class, self.current_test_method)
                finally:
                    self.__set_child_steps_to_parent()
                    self.__save_logs()

            log_print(f"{pad_string} passed  {exec_time(started)}", color='green')
        except (AssertionError, TidenException) as e:
            test_status = 'fail'
            test_exception = e
            tb_msg = traceback.format_exc()
        except Exception as e:
            test_status = 'error'
            test_exception = e
            tb_msg = traceback.format_exc()
        finally:
            if test_status != 'pass':
                log_print(tb_msg, color='red')
                log_print("{} {}  {}{}".format(pad_string,
                                               test_status,
                                               exec_time(started),
                                               known_issue_str(known_issue)),
                          color='red')
            self.result.stop_testcase(
                test_status,
                e=test_exception,
                tb=tb_msg,
                known_issue=known_issue,
                run_info=self.test_class.get_run_info() if hasattr(self.test_class, 'get_run_info') else None
            )

            # Execute test teardown method
            self.__call_test_setup_teardown('teardown')

            self.pm.do('after_test_method',
                       test_status=test_status,
                       exception=test_exception,
                       stacktrace=tb_msg,
                       known_issue=known_issue,
                       description=getattr(self.test_class, self.current_test_method, lambda: None).__doc__,
                       inner_report_config=getattr(self, '_secret_report_storage'))
            # Kill java process if teardown function didn't kill nodes
            if not hasattr(self.test_class, 'keep_ignite_between_tests'):
                kill_stalled_java(self.ssh_pool)

            return test_status

    @step('logs')
    def __save_logs(self):
        test_dir = self.config.get('rt', {}).get('remote', {}).get('test_dir')
        if 'WardReport' in self.config.get('plugins', []):
            report_config = self.config['plugins']['WardReport']
            files_receiver_url = report_config['files_url']
            upload_logs = report_config['upload_logs']
        else:
            return
        if test_dir:
            try:
                for host_ip, output_lines in self.ssh_pool.exec([f"ls {test_dir}"]).items():
                    with Step(self, host_ip):
                        for line in output_lines:
                            file_name: str
                            for file_name in line.split('\n'):
                                if file_name and file_name.endswith('.log'):
                                    send_file_name = f'{uuid4()}_{file_name}'
                                    add_attachment(self, file_name, send_file_name, AttachmentType.FILE)
                                    if upload_logs:
                                        cmd = f'cd {test_dir}; ' \
                                              f'curl -H "filename: {send_file_name}" ' \
                                              f'-F "file=@{file_name};filename={file_name}" ' \
                                              f'{files_receiver_url}/files/add'
                                        self.ssh_pool.exec_on_host(host_ip, [cmd])
            except:
                log_print(f'Failed to send report. \n{format_exc()}', color='pink')

    def __copy_resources_to_local_test_module_directory(self):
        """
        Copy resources in test resource directory
        :return:
        """
        test_resource_dir = "%s/res" % self.config['rt']['test_module_dir']
        if not path.exists(test_resource_dir):
            mkdir(test_resource_dir)
            self.config['rt']['resource_dir'] = "%s/res/%s" % (self.config['suite_dir'], self.module_short_name[5:])
            for file in glob("%s/*" % self.config['rt']['resource_dir']):
                if path.isfile(file):
                    copyfile(file, f"{test_resource_dir}/{basename(file)}")
        self.config['rt']['test_resource_dir'] = unix_path(test_resource_dir)

    def __create_test_module_directory(self, remote_test_module_dir, test_module_dir):
        mkdir(test_module_dir)
        self.ssh_pool.exec([f'mkdir -p {remote_test_module_dir}'])

    @step('{method_name}')
    def __call_test_setup_teardown(self, method_name):
        method_to_execute = None
        try:
            self._call_plugin_manager(f'before_test_method_{method_name}')
            all_tests = self.test_plan[self.test_module].all_tests

            if all_tests[self.current_test_name].get(f'{method_name}_test_method'):
                method_to_execute = all_tests[self.current_test_name].get(f'{method_name}_test_method')
                self.__print_with_format(msg=str(method_to_execute.__name__))
                try:
                    if all_tests[self.current_test_name].get(f'{method_name}_test_params'):
                        method_to_execute(self.test_class)
                    else:
                        method_to_execute()
                except Exception as e:
                    log_print(f'!!! Exception in {method_name} code !!!', color='red')
                    log_print(traceback.format_exc())
                    try:
                        self.__save_logs()
                    except:
                        log_print(f'Failed to get logs\n{traceback.format_exc()}', color='pink')

                    # if exception in setup method then re-raise the exception as we should fail the test
                    if method_name == 'setup':
                        raise e
        finally:
            self.__set_child_steps_to_parent()

        self._call_plugin_manager(f'after_test_method_{method_name}')

    def __set_child_steps_to_parent(self):
        exec_report: InnerReportConfig = getattr(self.test_class, '_secret_report_storage', None)
        test_report: InnerReportConfig = getattr(self, '_secret_report_storage')
        idx_to_add = None
        for idx, test_step in enumerate(test_report.steps):
            if test_step['status'] is None:
                idx_to_add = idx
                break
        test_report.steps[idx_to_add]['children'] = exec_report.steps + test_report.steps[idx_to_add].get('children', [])
        title = getattr(getattr(self.test_class, self.current_test_method), '__report_title__', None)
        suites = getattr(getattr(self.test_class, self.current_test_method), '__report_suites__', None)
        if title:
            test_report.title = title
            test_report.suites = suites
        setattr(self, '_secret_report_storage', test_report)
        setattr(self.test_class, '_secret_report_storage', InnerReportConfig())

    def __call_module_setup_teardown(self, fixture_name):
        """
        Execute test module setup/teardown fixture.
        :param fixture_name: either 'setup' or 'teardown'
        :return:
        """
        self._call_plugin_manager('before_test_class_%s' % fixture_name)
        fixture_passed = True
        try:
            if hasattr(self.test_class, fixture_name):
                started = time()
                try:
                    self.__print_with_format('started', current_method_name=fixture_name)
                    self.__update_config_and_save(current_method_name=fixture_name)

                    # Execute setup or teardown method
                    call_method(self.test_class, fixture_name)
                    self.__print_with_format('finished in %s sec' % (int(time() - started)),
                                             current_method_name=fixture_name)
                # except (AssertionError, TidenException) as e:
                except Exception as e:
                    fixture_passed = False
                    self.__print_with_format('failed in %s sec' % (int(time() - started)),
                                             current_method_name=fixture_name)
                    log_print('Exception in %s.%s.%s: %s\n%s' %
                              (self.test_module, self.test_class_name, fixture_name,
                               str(e), str(traceback.format_exc())), color='red')
        finally:
            self._call_plugin_manager('after_test_class_%s' % fixture_name)
            return fixture_passed

    def _call_plugin_manager(self, execution_point):
        args = [self.test_module, self.test_class]
        if self.current_test_method:
            args.append(self.current_test_method)

        self.pm.do(execution_point, *args)

    def __update_config_and_save(self, current_method_name=None):
        test_method = current_method_name if current_method_name else self.current_test_method
        test_method_name = test_method.split('(')[0] if '(' in test_method else test_method
        test_dir_name = test_method_name

        all_tests = self.test_plan[self.test_module].all_tests
        # cause of repeated_tests decorator
        if all_tests.get(test_method) and all_tests[test_method].get('repeated_test_name'):
            test_dir_name = '{}_{}'.format(
                test_method_name,
                all_tests[test_method].get('repeated_test_name')[self.test_iteration])

        self.config['rt']['test_method'] = test_method_name
        self.config['rt']['remote']['test_dir'] = "{}/{}/{}".format(
            self.config['rt']['remote']['test_module_dir'],
            self.config['rt']['test_class'],
            test_dir_name
        )
        self.config['rt']['test_dir'] = "{}/{}/{}".format(
            self.config['rt']['test_module_dir'], self.config['rt']['test_class'], test_dir_name)
        try:
            create_remote_dir = [
                'mkdir -p %s/%s/%s' % (self.config['rt']['remote']['test_module_dir'],
                                       self.test_class_name, str(test_dir_name)),
                'ln -sfn %s %s/current_test_directory' % (self.config['rt']['remote']['test_module_dir'],
                                                          self.config['environment']['home'])
            ]
            self.ssh_pool.exec(create_remote_dir)
        except Exception:
            log_print("Can't create symlink to current test", color='red')
        self._save_config()

    def _check_test_for_skip(self):
        attribs = []
        skip_test = False
        skip_msg = None
        skip_no_start = False

        test_function = getattr(self.test_class, self.current_test_method)
        if hasattr(test_function, "__attrib__"):
            attribs = getattr(test_function, "__attrib__")
        attribs.append(str(self.current_test_method))

        # if attr is passed to runner and test is not marked with one of the attribute
        # then skip it.
        if 'mute' in attribs:
            skip_msg = 'skipped cause test is MUTED'

            known_issue = None
            if hasattr(test_function, "__known_issues__"):
                known_issue = getattr(test_function, "__known_issues__")
            if known_issue:
                skip_msg = '{} cause of {}'.format(skip_msg, known_issue)

            skip_test = True
            skip_no_start = True

        elif self.config.get('attrib') and should_be_skipped(self.config.get('attrib'), attribs,
                                                           self.config.get('attr_match', 'any')):
            skip_msg = 'skipped cause of attrib mismatch'
            skip_test = True
            skip_no_start = True

        if hasattr(test_function, "__skipped__"):
            skip_msg = 'skipped cause of %s' % test_function.__skipped_message__
            skip_test = True

        if hasattr(test_function, "__skip_cond__"):
            skip_condition = getattr(test_function, "__skip_cond__")
            conditions_met, skip_message = skip_condition(self.config)
            if not conditions_met:
                skip_msg = 'skipped cause of %s' % skip_message
                skip_test = True

        if hasattr(test_function, "__skip_conds__") and \
                len(test_function.__skip_conds__) > 0:
            skip_conditions = test_function.__skip_conds__
            for skip_condition in skip_conditions:
                conditions_met, skip_message = skip_condition(self.test_class)
                if not conditions_met:
                    skip_msg = 'skipped cause of %s' % skip_message
                    skip_test = True

        return skip_test, skip_msg, skip_no_start

    def get_tests_results(self):
        return self.result

    def _save_config(self):
        write_yaml_file(self.config['config_path'], self.config)

    @staticmethod
    def gen_tests(test_class):
        """
        Generates all test method of given test class
        :param test_class:
        :return:
        """
        for class_attr in dir(test_class):
            if class_attr.startswith('test_'):
                yield class_attr

    def collect_tests0(self, test_method_names):
        """
        Collect given set of tests from test module for all configurations
        :param test_method_names:
        :return:
        """
        if not hasattr(self.test_class, '__configurations__'):
            self.collect_tests1(test_method_names)
        else:
            cfg_options = getattr(self.test_class, '__configuration_options__').copy()
            configurations = getattr(self.test_class, '__configurations__').copy()

            for configuration in configurations:
                # set configuration options from given configuration to Tiden config,
                # so that test can check options and skip itself
                set_configuration_options(cfg_options, self.config, configuration)

                self.collect_tests1(test_method_names, common_test_param={
                    'configuration': configuration,
                    'cfg_options': cfg_options,
                })

    def collect_tests1(self, test_method_names, common_test_param={}):
        """
        Collect given tests from current test module
        :param test_method_names:
        :param common_test_param:
        :return:
        """
        try:
            test_plan = self.test_plan[self.test_module]
            for test_method_name in test_method_names:
                self.__prepare_test_vars(test_method_name, **common_test_param)

                test_param = {
                    'test_method_name': test_method_name,
                }
                is_skipped, skip_msg, skip_no_start = self._check_test_for_skip()
                test_param.update(self.collect_test0())

                repeat_count = test_param.get('repeated_test_count', 1)
                if repeat_count > 0:
                    if repeat_count == 1:
                        # don't rename tests when only one iteration requested
                        test_param['repeated_test_name'] = []

                else:
                    # rare case, skip by --to=repeated_test.test_name=0
                    is_skipped = True
                    skip_msg = 'skipped due to repeated_test iterations <= 0'
                    skip_no_start = False

                if is_skipped:
                    test_param.update({
                        'skip_msg': skip_msg,
                        'skip_no_start': skip_no_start,
                    })
                    test_plan.skipped_tests.append(self.current_test_name)
                else:
                    if common_test_param:
                        test_param.update(common_test_param)

                    test_plan.tests_to_execute.append(self.current_test_name)

                test_plan.all_tests[self.current_test_name] = test_param.copy()
        finally:
            self.current_test_method = None
            self.current_test_name = None

    def __print_found_test_method_to_execute(self, long_path_len, test_cnt, test_module):
        method_long_name = "%s.%s.%s " % (test_module, self.test_class_name, self.current_test_name)
        pad_string = method_long_name.ljust(long_path_len, '.')
        log_print("%s found (%s from %s)" % (pad_string, test_cnt, len(self.total.tests_to_execute)), color='yellow')

    def __print_with_format(self, msg='', current_method_name=''):
        if not current_method_name:
            if self.current_test_method:
                current_method_name = self.current_test_method
            else:
                current_method_name = ''
        log_print("[{}][.{}.{}] {}".format(
            datetime.now().isoformat()[11:-7],
            self.test_class_name,
            current_method_name,
            msg))

    def __print_current_module_name(self):
        log_print("[%s][%s]" % (
            datetime.now().isoformat()[11:-7], self.test_module))

    def __get_pad_string(self, msg=None):
        return ("%s.%s.%s " % (
            self.test_module, self.test_class_name, msg if msg else self.current_test_method)) \
            .ljust(self.long_path_len, '.')

