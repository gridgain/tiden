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


import sys
from os.path import basename
from unittest.mock import patch
from importlib import import_module

from ..tidenfabric import TidenFabric
from ..util import log_print

allowed_commands = {
    'run-tests': 'tiden.console.entry_points.run_tests',
}


def usage(self_name):
    print('Usage: ' + self_name + ' <command> <args> <options>')
    print('')
    print('Where <command> is one of:')
    padding_len = max([len(command) for command in allowed_commands.keys()])
    for command, package in allowed_commands.items():
        print('')
        module = import_module(package)
        padding = (" " * (padding_len - len(command)))
        description = ''
        if module.__doc__:
            description = module.__doc__
        elif hasattr(module, 'main'):
            main = getattr(module, 'main')
            if main.__doc__:
                description = main.__doc__
        print(command + padding + '\t' + description.rstrip())
        if hasattr(module, 'create_parser'):
            for line in module.create_parser().format_help().rstrip().split('\n'):
                print('\t' + line)


def main():
    hook_mgr = TidenFabric().get_hook_mgr()
    allowed_commands = {}
    entry_points_list = hook_mgr.hook.tiden_get_entry_points()
    for entry_points in entry_points_list:
        allowed_commands.update(entry_points)

    if len(sys.argv) <= 1:
        usage(basename(sys.argv[0]))
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd not in allowed_commands:
        usage(basename(sys.argv[0]))
        sys.exit(1)

    args = sys.argv[1:]
    module = import_module(allowed_commands[cmd])
    if not module or not hasattr(module, 'main'):
        log_print(f'ERROR: Can\'t find module {cmd} entry point', color='red')
    with patch.object(sys, 'argv', args):
        module.main()
