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


class TeamcityIntegration(TidenPlugin):

    def _format_stacktrace(self, text):
        """
        Format stacktrace for TC
        Escape characters need to be changed to |

        https://www.jetbrains.com/help/teamcity/build-script-interaction-with-teamcity.html#BuildScriptInteractionwithTeamCity-Escapedvalues
        """
        for symbol in "|'[]":
            text = text.replace(symbol, f'|{symbol}')
        if '\n' in text:
            text = text.replace('\n', '|n')
        if '\r' in text:
            text = text.replace('\r', '|r')
        if '\t' in text:
            text = text.replace('\t', '|t')
        return text

    def before_test_method(self, *args, **kwargs):
        test_name = kwargs.get('test_name')
        time_stamp = datetime.now().isoformat()[:-3]
        test_name = self._format_stacktrace(test_name)

        log_print(f"##teamcity[testStarted timestamp='{time_stamp}' name='{test_name}']")

    def after_test_method(self, *args, **kwargs):
        test_name = kwargs.get('test_name')
        exception_details = kwargs.get('stacktrace')
        exception = str(kwargs.get('exception'))
        status = kwargs.get('test_status')
        time_stamp = datetime.now().isoformat()[:-3]
        test_name = self._format_stacktrace(test_name)

        if status == 'pass':
            log_print(f"##teamcity[testFinished timestamp='{time_stamp}' name='{test_name}']")
        else:
            log_print(f"##teamcity[testFailed "
                      f"timestamp='{time_stamp}' "
                      f"name='{test_name}' "
                      f"message='{self._format_stacktrace(exception)}' "
                      f"details='{self._format_stacktrace(exception_details)}']")
