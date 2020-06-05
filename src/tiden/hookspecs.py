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

import pluggy

hookspec = pluggy.HookspecMarker("tiden")


@hookspec
def tiden_get_applications_path():
    """
    Return list of applications packages search path (import prefixes).

    Default applications packages prefixes list is:
    ["tiden.apps.", "apps"]
    """


@hookspec
def tiden_get_plugins_path():
    """
    Return list of plugins search path (actual file system paths).

    Default list:
    [<tiden install path>/plugins, <current working directory>/plugins]
    """

@hookspec
def tiden_get_entry_points():
    """
    Return dictionary of tiden entry point packages.

    Default: {
        'run-tests': 'tiden.console.entry_points.run_tests',
        'merge-reports': 'tiden.console.entry_points.merge_yaml_reports',
        'prepare-apache-builds': 'tiden.console.entry_points.prepare_apache_builds',
    }
    """
