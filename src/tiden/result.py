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

from time import time
from .util import exec_time, make_number, log_print
import traceback
import xml.etree.ElementTree as ET
import re
from os import path
from copy import deepcopy


class Result:
    re_escape_seq = re.compile(r'(\x1b\[|\x9b)[^@-_]*[@-_]|\x1b[@-_]', re.I)
    statuses = ['pass', 'fail', 'error', 'skip', 'total']
    testcase_started = None

    def __init__(self, **kwargs):
        self.tests = {}
        self.started = int(time())
        self.passed_with_issue = {}
        self.tests_num = {
            'total': 0,
            'pass': 0,
            'fail': 0,
            'error': 0,
            'skip': 0
        }
        self.tested_class = None
        self.tested_attr = None
        self.current_test = None
        # if kwargs.get('path') is not None:
        #     self.tiden_path = kwargs.get('path')
        self.xunit_path = None
        self.xunit_test = None
        if kwargs.get('xunit_path') is not None:
            self.xunit_path = kwargs.get('xunit_path')
            suite_attributes = {
                'name': "tiden",
                "tests": str(0),
                "errors": str(0),
                "failures": str(0),
                "skipped": str(0),
                "time": str(0),
            }
            self.xunit = ET.Element('testsuite', suite_attributes)
            self.flush_xunit()

    def start_testcase(self, tested_class, tested_attr):
        from tiden.tidenfabric import TidenFabric
        result_lines_collector = TidenFabric().getResultLinesCollector()
        result_lines_collector.reset()
        self.testcase_started = time()
        self.tested_class = tested_class
        self.tested_attr = tested_attr
        tested_attr_name = tested_attr.split('(')[0] if '(' in tested_attr else tested_attr
        self.current_test = "{}.{}.{}".format(tested_class.__module__, tested_class.__class__.__name__, tested_attr)
        test_case_id = None

        if hasattr(getattr(tested_class.__class__, tested_attr_name), "__test_id__"):
            test_ids = (getattr(getattr(tested_class.__class__, tested_attr_name), "__test_id__"))
            test_case_id = int(test_ids[0])
            if test_case_id == 0:
                test_case_id = None

        if self.tests.get(self.current_test):
            self.tests[self.current_test].update({
                "started": time(),
            })
        else:
            self.tests_num['total'] += 1
            self.tests[self.current_test] = {
                'status': 'running',
                'classname': "%s.%s" % (tested_class.__module__, tested_class.__class__.__name__),
                'name': str(tested_attr),
                'time': str(0),
                'started': time()
            }
            if test_case_id:
                self.tests[self.current_test].update({
                    'test_case_id': test_case_id,
                })

    def skip_testcase_no_start(self, tested_class, tested_attr, skip_message=None, skip_no_start=False):
        self.tests_num['total'] += 1
        self.tests_num['skip'] += 1
        test_case_id = ''
        self.current_test = "%s.%s.%s" % (tested_class.__module__, tested_class.__class__.__name__, tested_attr)

        tested_attr_name = tested_attr.split('(')[0] if '(' in tested_attr else tested_attr

        if hasattr(getattr(tested_class.__class__, tested_attr_name), "__test_id__"):
            test_ids = (getattr(getattr(tested_class.__class__, tested_attr_name), "__test_id__"))
            test_case_id = int(test_ids[0])

        self.tests[self.current_test] = {
            'status': 'skipped_no_start' if skip_no_start else 'skipped',
            'classname': "%s.%s" % (tested_class.__module__, tested_class.__class__.__name__),
            'test_case_id': test_case_id,
            'name': str(tested_attr),
            'time': str(0),
            'started': time(),
            'xunit_info': {
                # 'type': "skipped",
                # 'message': self.get_skip_message(skip_message)
                'type': self.get_skip_message(skip_message),
            }
        }

    def skip_testcase(self, skip_message=None):
        self.tests_num['skip'] += 1
        self.tests[self.current_test]['status'] = "skipped"
        self.tests[self.current_test]['xunit_info'] = {
            'type': "skipped",
            'message': self.get_skip_message(skip_message)
        }

    def get_skip_message(self, skip_message):
        if skip_message is None:
            skip_message = getattr(self.tested_class, self.tested_attr).__skipped_message__
        return self.util_filter_escape_seqs(skip_message)

    def pass_test(self):
        self.tests_num['pass'] += 1
        self.tests[self.current_test]['status'] = "pass"

    def fail_test(self, e):
        self.tests_num['fail'] += 1
        self.tests[self.current_test]['status'] = "failure"
        self.tests[self.current_test]['xunit_info'] = {
            'type': e.__class__.__name__,
            'message': self.util_filter_escape_seqs(str(traceback.format_exc()))
        }

    def error_test(self, e):
        self.tests_num['error'] += 1
        self.tests[self.current_test]['status'] = "errors"
        self.tests[self.current_test]['xunit_info'] = {
            'type': e.__class__.__name__,
            'message': self.util_filter_escape_seqs(str(traceback.format_exc()))
        }

    def stop_testcase(self, status, **kwargs):
        from tiden.tidenfabric import TidenFabric
        result_lines_collector = TidenFabric().getResultLinesCollector()
        test_result_lines = result_lines_collector.get_lines()

        # do not change fail status in iterations
        if self.tests[self.current_test]['status'] == 'fail':
            return

        if self.tests[self.current_test]['status'] != status:
            if self.tests[self.current_test]['status'] != 'running':
                prev_status = self.tests[self.current_test]['status']
                self.tests_num[prev_status] -= 1

            self.tests_num[status] += 1
            self.tests[self.current_test]['status'] = status

        self.tests[self.current_test]['time'] = str(exec_time(self.testcase_started, 1))

        if status != 'pass':
            self.tests[self.current_test]['xunit_info'] = {
                'type': kwargs.get('e').__class__.__name__,
                'message': self.util_filter_escape_seqs('\n'.join(test_result_lines) + str(kwargs.get('tb')))
            }
        else:
            self.tests[self.current_test]['xunit_info'] = {
                'type': None,
                'message': None if not test_result_lines else self.util_filter_escape_seqs('\n'.join(test_result_lines))
            }

        if kwargs.get('known_issue'):
            self.tests[self.current_test]['known_issue'] = kwargs.get('known_issue')
            if self.tests[self.current_test]['status'] == "pass":
                self.passed_with_issue[self.current_test] = kwargs.get('known_issue')

            message = self.tests[self.current_test]['xunit_info']['message']
            if message is None:
                message = ''

            if self.tests[self.current_test].get('xunit_info'):
                self.tests[self.current_test]['xunit_info']['message'] = \
                    "*** Known issue: %s\n" % kwargs.get('known_issue') \
                    + message

        if kwargs.get('run_info'):
            self.tests[self.current_test]['run_info'] = kwargs.get('run_info')

        self.update_xunit()

    def update_xunit(self):
        if self.xunit is not None:
            for xunit_status, status in zip(
                    ['tests', 'failures', 'errors', 'skipped'],
                    ['total', 'fail', 'error', 'skip']
            ):
                self.xunit.attrib[xunit_status] = str(self.tests_num[status])
            self.xunit.attrib['time'] = str(sum([int(test['time']) for test in self.tests.values()]))
            self.xunit_test = ET.SubElement(
                self.xunit,
                'testcase',
                {
                    'classname': "%s" % (self.tests[self.current_test]['classname']),
                    'name': self.tests[self.current_test]['name'],
                    "time": self.tests[self.current_test]['time']
                }
            )

            if self.tests[self.current_test]['status'] != 'pass':
                element_name = self.tests[self.current_test]['status']
                if element_name == 'errors':
                    element_name = 'error'
                if element_name == 'fail':
                    element_name = 'failure'
                ET.SubElement(self.xunit_test,
                              element_name,
                              self.tests[self.current_test]['xunit_info'])

            self.flush_xunit()

    def flush_xunit(self):
        tree = ET.ElementTree(self.xunit)
        tree.write(self.xunit_path, xml_declaration=True)

    def get_tests_num(self, test_type):
        return self.tests_num[test_type]

    def get_started(self):
        return self.started

    def print_tests_details(self, status):
        for test in self.tests.keys():
            if self.tests[test].get('status') == status:
                log_print('-------------------------------------------', color='red')
                log_print('Test {} ({}) failed with error:'.format(test, self.tests[test].get('classname')), color='red')
                log_print('-------------------------------------------', color='red')
                if self.tests[test].get('known_issue'):
                    log_print('Found known issue for this test: {}'.format(self.tests[test].get('known_issue')), color='blue')
                log_print('{}'.format(self.util_filter_escape_seqs(self.tests[test]['xunit_info']['message'])), color='red')

    def get_summary(self):
        return "Passed/failed/errors/skipped/total tests are %s/%s/%s/%s/%s" % (
                self.tests_num['pass'],
                self.tests_num['fail'],
                self.tests_num['error'],
                self.tests_num['skip'],
                self.tests_num['total'],
        )

    def print_summary(self):
        if self.tests_num['error'] != 0:
            self.print_tests_details('error')
        if self.tests_num['fail'] != 0:
            self.print_tests_details('fail')

        log_print("*** Summary ***", color='blue')
        log_print(
            "Passed/failed/errors/skipped/total tests are {}/{}/{}/{}/{}".format
            (
                self.tests_num['pass'],
                self.tests_num['fail'],
                self.tests_num['error'],
                self.tests_num['skip'],
                self.tests_num['total'],
            ), color='blue'
        )
        self.get_passed_with_issue()
        log_print('xUnit report stored to {}'.format(self.xunit_path), color='debug')

    def create_testrail_report(self, config, report_file=None):
        testrail_report_info = {}
        run_id_timestamp = "%s" % time()
        ignite_properties = {
            'ignite_revision': '0',
            'ignite_version': '0',
        }

        if config.get('environment'):
            env_config = config.get('environment')

            self.test_run_options = {
                'hosts number': len(env_config.get('server_hosts')),
                'server nodes number': len(env_config.get('server_hosts')) * int(env_config.get('servers_per_host', 1)),
                'client nodes number': len(env_config.get('client_hosts')) * int(env_config.get('clients_per_host', 1)),
                'caches number': 0,
            }
        else:
            self.test_run_options = {
                'hosts number': 0,
                'server nodes number': 0,
                'client nodes number': 0,
                'caches number': 0,
            }

        for artifact in config.get('artifacts', {}).keys():
            if config['artifacts'][artifact].get('type') == 'ignite':
                ignite_properties = {
                    'ignite_build': config['artifacts'][artifact]['ignite_build'],
                    'ignite_rel_date': config['artifacts'][artifact]['ignite_rel_date'],
                    'ignite_revision': config['artifacts'][artifact]['ignite_revision'],
                    'ignite_version': config['artifacts'][artifact]['ignite_version']
                }
                if config['artifacts'][artifact].get('gridgain_version'):
                    ignite_properties.update({
                        'gridgain_build': config['artifacts'][artifact]['gridgain_build'],
                        'gridgain_revision': config['artifacts'][artifact]['gridgain_revision'],
                        'gridgain_version': config['artifacts'][artifact]['gridgain_version']
                    })
                # In case of multiple artifacts, the 'report' flag will tell which ignite version to pick
                if config['artifacts'][artifact].get('report') is True:
                    break

        for test in self.tests:
            suite_name = self.tests[test]['classname'].split('.')[2]
            class_name = self.tests[test]['classname']
            tr_status = self.util_status_to_testrail_status(self.tests[test]['status'])

            function_name = self.tests[test]['name']
            configuration = {}
            configuration_options = []
            if '(' in function_name:
                # test with configuration
                function_name, configuration_representation = function_name.split('(')
                # strip tail ')'
                configuration_representation = configuration_representation[:-1]
                cfg_options = configuration_representation.split(', ')
                for cfg_option in cfg_options:
                    cfg_option_name, cfg_option_value = cfg_option.split('=')
                    configuration_options.append(cfg_option_name)
                    if '_enabled' in cfg_option_name:
                        configuration[cfg_option_name] = cfg_option_value.lower() == 'true'
                    else:
                        configuration[cfg_option_name] = make_number(cfg_option_value)

            if tr_status == 'skipped' or tr_status == 'not started':
                message = self.tests[test].get('xunit_info', {}).get('type', '')
            else:
                message = self.tests[test].get('xunit_info', {}).get('message', '')
            assert_section = [{'status': tr_status}]
            if tr_status not in ['passed']:
                assert_section = [{'status': tr_status, 'message': message}]
            else:
                if message:
                    assert_section = [{'status': tr_status, 'message': message}]

            run_info = deepcopy(self.test_run_options)
            if self.tests[test].get('run_info'):
                for param, value in self.tests[test]['run_info'].items():
                    if param in ['servers', 'clients']:
                        run_info[param[0:-1] + ' nodes number'] = value
                    else:
                        run_info[param] = value

            self.tests[test]['run_info'] = run_info

            test_run_id = "%s-%s" % (suite_name, self.tests[test]['started'],)
            testrail_report_info[test_run_id] = {
                'asserts': assert_section,
                'last_status': tr_status,
                'module': class_name,
                'function': function_name,
                'test_run_id': test_run_id,
                'suite_run_id': "%s-%s" % (suite_name, run_id_timestamp),
                'ignite_properties': ignite_properties,
                'test_configuration_options': configuration_options.copy(),
            }
            if tr_status not in ['skipped', 'not started']:
                testrail_report_info[test_run_id]['test_run_options'] = self.tests[test].get('run_info')

            for additional_opt in ['test_case_id', 'known_issue']:
                if self.tests[test].get(additional_opt):
                    testrail_report_info[test_run_id].update({
                        additional_opt: self.tests[test][additional_opt],
                    })
            testrail_report_info[test_run_id].update(configuration)

        if report_file:
            file_name = report_file
        else:
            file_name = 'testrail_report.yaml'

        test_report_path = '%s/%s' % ('/'.join(list(path.split(self.xunit_path)[:-1])), file_name)

        Result._save_test_report(testrail_report_info, test_report_path)

    def get_passed_with_issue(self, print_stat=True):
        if print_stat and self.passed_with_issue:
            log_print('WARNING: these tests marked with known issue but PASSED:\nTEST\tKNOWN ISSUE', color='red')
            for test_name in self.passed_with_issue:
                log_print('%s\t%s' % (test_name, self.passed_with_issue.get(test_name)), color='red')

        return self.passed_with_issue if self.passed_with_issue else {}

    @staticmethod
    def util_status_to_testrail_status(status):
        status_to_testrail = {
            'pass': 'passed',
            'failure': 'failed',
            'fail': 'failed',
            'errors': 'failed',
            'error': 'failed',
            'skipped': 'skipped',
            'skipped_no_start': 'not started',
        }
        return status_to_testrail.get(status)

    @staticmethod
    def _save_test_report(report, filename):
        import yaml

        with open(filename, 'w') as w:
            yaml.dump(report, stream=w, line_break=True)

        log_print('TestRail report stored to %s' % filename, color='debug')

    def util_filter_escape_seqs(self, s):
        return self.re_escape_seq.sub('', s)

    def get_tests(self):
        from copy import deepcopy
        return deepcopy(self.tests)

    def get_test_details(self, test_name):
        """
        return test status, xunit test error type error/failure, xunit test error message, original test name
        :param test_name:
        :return:
        """
        if self.tests.get(test_name) and self.tests.get(test_name).get('status'):
            if self.tests[test_name].get('xunit_info'):
                current_test = self.tests.get(test_name)
                return current_test.get('status'), current_test['xunit_info'].get('type'), \
                       current_test['xunit_info'].get('message'), current_test.get('name')
            else:
                return self.tests.get(test_name).get('status'), None, None, self.tests.get(test_name).get('name')
        else:
            return None, None, None, None

    def update_test_name(self, new_name, old_name=None):
        """
        Update test name in the internal dict. If old_name is None current test name will be changed.
        :param new_name:
        :param old_name:
        :return:
        """
        old_name = old_name if old_name else self.current_test
        full_class_name = self.tests.get(old_name).get('classname')
        self.tests['{}.{}'.format(full_class_name, new_name)] = self.tests.pop(old_name)


class ResultLinesCollector:
    def __init__(self, config):
        self.config = config
        self.lines = []

    def reset(self):
        self.lines = []

    def add_line(self, message):
        self.lines.append(message)

    def get_lines(self):
        return self.lines

