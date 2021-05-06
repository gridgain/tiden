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

from datetime import datetime
from os import environ
from time import time
from uuid import uuid4
from re import sub, search
from traceback import format_exc

from requests import post

from tiden.tidenplugin import TidenPlugin
from tiden.report.steps import InnerReportConfig

TIDEN_PLUGIN_VERSION = '1.0.0'


class WardReport(TidenPlugin):

    statuses_parse = {
        'pass': 'passed',
        'fail': 'failed',
        'error': 'failed'
    }

    def __init__(self, *args, **kwargs):
        TidenPlugin.__init__(self, *args, **kwargs)

        self.report_url = self.options['url']
        self.files_report_url = self.options['files_url']
        self.upload_logs = self.options['upload_logs']
        self.tc_build_id = self.options.get('tc_build_id')
        self.force_report_as_release = self.options.get('report_as_release', None)
        self.main_section = self.options.get('section', 'Distributed tests')
        self.run_id = str(uuid4())
        self.current_report: dict = {}

    def report_base(self):
        result = {
            'title': '',
            'test_case_id': 0,
            'run_id': self.run_id,
            'time': {
                'start': 0,
                'start_pretty': '',
                'end': 0,
                'end_pretty': '',
                'diff': ''
            },
            'status': '',
            'data': {},
            'steps': [],
            'suites': [],
            'description': '',
        }
        if environ.get('BUILD_URL'):
            result['data']['jenkins_build_url'] = environ['BUILD_URL']
        elif self.tc_build_id:
            result['data']['tc_build_id'] = self.tc_build_id
        return result

    def pretty_datetime(self, time):
        return datetime.fromtimestamp(time).isoformat().replace('T', ' ')

    def find_version(self, artifacts: dict):
        found_version = None
        if environ.get('GRIDGAIN_VERSION'):
            found_version = environ['GRIDGAIN_VERSION']
        else:
            for config in artifacts.values():
                if config.get('gridgain_version'):
                    found_version = config['gridgain_version']

        if found_version is None:
            found_version = 'unknown version'
        return found_version

    def find_suites(self, module_name: str, test_name: str):
        suites_base = [module_name.split('.')[1].replace('test_', '')]
        if '(' in test_name:
            suites_base.append(test_name[:test_name.index('(')].strip())
        return suites_base

    def modify_test_name(self, test_name):
        return sub(r'^test_(ignite_)?', '', test_name).replace('(', ' (')

    def before_test_method(self, *args, **kwargs):
        """
        Start report
        :param kwargs:
                test_module         'snapshots.test_snapshots'
                artifacts  :dict    All found artifacts
                test_name           'test_snapshot(wal_compaction=False,...)'
        """
        test_module = kwargs.get('test_module')
        artifacts = kwargs.get('artifacts')
        test_name = kwargs.get('test_name')
        if not test_module or not artifacts or not test_name:
            return

        self.current_report = self.report_base()
        self.current_report['title'] = self.modify_test_name(test_name)
        self.current_report['time']['start'] = round(time() * 1000)
        self.current_report['time']['start_pretty'] = self.pretty_datetime(time())

        self.current_report['suites'] = [self.main_section,
                                         self.find_version(artifacts),
                                         *self.find_suites(test_module, self.current_report['title'])]
        jenkins_job_name: str = environ.get('JOB_NAME')
        report_as_release_branch = jenkins_job_name and jenkins_job_name.startswith('release')
        if any([
            self.force_report_as_release == False,
            not report_as_release_branch and self.force_report_as_release is None
        ]):
            self.current_report['suites'].insert(1, 'Debug')

    def after_test_method(self, *args, **kwargs):
        """
        Send test reports
        :param kwargs:
                test_status     'passe'/'fail'
                exception       Exception name
                stacktrace      Exception stacktrace
                known_issue     Ticket ID
                description     Test method doc
        """
        status = kwargs.get('test_status')
        exception = kwargs.get('exception')
        stacktrace = kwargs.get('stacktrace')
        known_issue = kwargs.get('known_issue')
        description = kwargs.get('description')
        inner_report_config: InnerReportConfig = kwargs.get('inner_report_config')

        if not status or not self.current_report.get('title'):
            return

        test_status = self.statuses_parse.get(status)
        if not test_status:
            return

        self.current_report['data'] = self.current_report.get('data', {})
        if known_issue:
            self.current_report['data']['known_issues'] = [{'id': issue_id, 'message': 'known issue'} for issue_id in known_issue]
        self.current_report['time']['end'] = round(time() * 1000)
        self.current_report['time']['end_pretty'] = self.pretty_datetime(time())
        if description:
            self.current_report['description'] = description
        self._set_diff()
        self.current_report['status'] = test_status
        self.current_report['steps'] = inner_report_config.steps
        if inner_report_config.title:
            self.current_report['title'] = inner_report_config.title
        self.current_report['test_path'] = inner_report_config.test_path
        if inner_report_config.suites:
            self.current_report['suites'] = self.current_report['suites'] + inner_report_config.suites
        for field, value in inner_report_config.aux_fields.items():
            if value is None and self.current_report.get(field) is not None:
                self.current_report.pop(field)
            else:
                self.current_report[field] = value
        if exception:
            self.current_report['stacktrace'] = f'{exception}\n{stacktrace}'
        try:
            self.log_print('Sending test result to WARD')
            if post(f'{self.report_url}', json=self.current_report).status_code != 200:
                print(f'Failed to add: {self.current_report["title"]}')
        except:
            self.log_print(f'ERROR: Failed to send test. Please check if WARD is alive: https://ward.gridgain.com/tests/',
                           color='red')

    def _set_diff(self):
        diff = (self.current_report['time']['end'] - self.current_report['time']['start'])//1000
        if diff > 60:
            minutes = diff // 60
            pretty_diff = f'{diff // 60}m {diff - minutes * 60}s'
        else:
            pretty_diff = f'{diff}s'
        self.current_report['time']['diff'] = pretty_diff
