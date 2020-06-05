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

from . import hookimpl


@hookimpl
def tiden_get_applications_path():
    return ["tiden.apps.", "apps."]


@hookimpl
def tiden_get_plugins_path():
    from os.path import dirname, abspath, join
    from os import getcwd

    return [join(dirname(abspath(__file__)), "plugins"), join(abspath(getcwd()), "plugins")]


@hookimpl
def tiden_get_entry_points():
    from .console.main import allowed_commands
    return allowed_commands

