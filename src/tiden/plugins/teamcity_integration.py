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

from tiden import log_print
from tiden.tidenplugin import TidenPlugin

TIDEN_PLUGIN_VERSION = '1.0.0'


class TeamcityIntegrationPlugin(TidenPlugin):

    def before_test_method(self, *args, **kwargs):
        test_name = kwargs.get('test_name')
        time_stamp = datetime.now().isoformat()[:-3]

        log_print(f"##teamcity[testStarted timestamp='{time_stamp}' name='{test_name}']")

    def after_test_method(self, *args, **kwargs):
        test_name = kwargs.get('test_name')
        exception_details = kwargs.get('stacktrace')
        exception = str(kwargs.get('exception'))
        status = kwargs.get('test_status')
        time_stamp = datetime.now().isoformat()[:-3]

        if status == 'pass':
            log_print(f"##teamcity[testFinished timestamp='{time_stamp}' name='{test_name}']")
        else:
            log_print(f"##teamcity[testFailed timestamp='{time_stamp}' name='{test_name}' message='{exception}' details='{exception_details}']")
