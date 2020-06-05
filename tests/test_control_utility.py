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

import pytest
from pprint import PrettyPrinter
import os.path

from tiden.utilities.control_utility import ControlUtility

help_activate_deactivate_only = {
            'activate': 'activate',
            'deactivate': 'deactivate',
        }

commands_activate_deactivate_only = {
            'activate': '',
            'deactivate': '',
        }

help_2_4_baseline = {
            'activate cluster': 'activate',
            'deactivate cluster': 'deactivate',
            'print current cluster state': 'state',
            'print cluster baseline topology': 'baseline_print',
            'add nodes into baseline topology': 'baseline_add',
            'remove nodes from baseline topology': 'baseline_remove',
            'set baseline topology': 'baseline_set',
            'set baseline topology based on version': 'baseline_version',
        }

commands_2_4_no_force = {
            'activate': '',
            'deactivate': '',
            'state': '',
            'baseline_print': '',
            'baseline_add': '',
            'baseline_remove': '',
            'baseline_set': '',
            'baseline_version': '',
        }

commands_2_4_with_force = {
            'activate': '',
            'deactivate': '--force',
            'state': '',
            'baseline_print': '',
            'baseline_add': '--force',
            'baseline_remove': '--force',
            'baseline_set': '--force',
            'baseline_version': '--force',
        }

help_2_5_1_and_higher = {
            'activate cluster': 'activate',
            'deactivate cluster': 'deactivate',
            'print current cluster state': 'state',
            'print cluster baseline topology': 'baseline_print',
            'add nodes into baseline topology': 'baseline_add',
            'remove nodes from baseline topology': 'baseline_remove',
            'set baseline topology': 'baseline_set',
            'set baseline topology based on version': 'baseline_version',
            'list or kill transactions': 'tx',  # ['tx_list','tx_kill']
            'view caches information in a cluster. for more details type': 'view_caches',
        }

help_2_5_8_and_higher = {
            'activate cluster': 'activate',
            'deactivate cluster': 'deactivate',
            'print current cluster state': 'state',
            'print cluster baseline topology': 'baseline_print',
            'add nodes into baseline topology': 'baseline_add',
            'remove nodes from baseline topology': 'baseline_remove',
            'set baseline topology': 'baseline_set',
            'set baseline topology based on version': 'baseline_version',
            'list or kill transactions': 'tx',  # ['tx_list','tx_kill']
            'print detailed information (topology and key lock ownership) about specific transaction': 'tx_info',
            'view caches information in a cluster. for more details type': 'view_caches',
        }

commands_2_5_1_and_higher_with_force = {
            'activate': '',
            'deactivate': '--force',
            'state': '',
            'baseline_print': '',
            'baseline_add': '--force',
            'baseline_remove': '--force',
            'baseline_set': '--force',
            'baseline_version': '--force',
            'tx': '--force',
            # 'tx_list': '',
            # 'tx_kill': '--force',
            'view_caches': '',
}

commands_2_5_1_and_higher_with_yes = {
            'activate': '',
            'deactivate': '--yes',
            'state': '',
            'baseline_print': '',
            'baseline_add': '--yes',
            'baseline_remove': '--yes',
            'baseline_set': '--yes',
            'baseline_version': '--yes',
            'tx': '--yes',
            # 'tx_list': '',
            # 'tx_kill': '--force',
            'view_caches': '',
}

commands_2_5_8_and_higher_with_yes = {
            'activate': '',
            'deactivate': '--yes',
            'state': '',
            'baseline_print': '',
            'baseline_add': '--yes',
            'baseline_remove': '--yes',
            'baseline_set': '--yes',
            'baseline_version': '--yes',
            'tx': '--yes',
            'tx_info': '',
            # 'tx_list': '',
            # 'tx_kill': '--force',
            'view_caches': '',
}

testdata = [
    {
        # No control.sh in 7.9.13
        'ignite_version': '1.9.13',
        'help': {
        },
        'commands': {
        },
    },
    {
        # Old format of commands: only --activate and --deactivate, no force flag
        'ignite_version': '2.1.12',
        'help': help_activate_deactivate_only,
        'commands': commands_activate_deactivate_only,
    },
    {
        # Old format of commands: only --activate and --deactivate, no force flag
        'ignite_version': '2.3.1',
        'help': help_activate_deactivate_only,
        'commands': commands_activate_deactivate_only,
    },
    {
        # New format, no --force at all
        'ignite_version': '2.4.0',
        'help': help_2_4_baseline,
        'commands': commands_2_4_no_force,
    },
    {
        # added --force
        'ignite_version': '2.4.6-p1',
        'help': help_2_4_baseline,
        'commands': commands_2_4_with_force,
    },
    {
        # added --force
        'ignite_version': '2.4.8-p10',
        'help': help_2_4_baseline,
        'commands': commands_2_4_with_force,
    },
    {
        'ignite_version': '2.5.1-p6',
        'help': help_2_5_1_and_higher,
        'commands': commands_2_5_1_and_higher_with_force,
    },
    {
        'ignite_version': '2.5.1-p10',
        'help': help_2_5_1_and_higher,
        'commands': commands_2_5_1_and_higher_with_yes,
    },
    {
        'ignite_version': '2.5.1-p14',
        'help': help_2_5_1_and_higher,
        'commands': commands_2_5_1_and_higher_with_yes,
    },
    {
        'ignite_version': '2.5.1-p160',
        'help': help_2_5_1_and_higher,
        'commands': commands_2_5_1_and_higher_with_yes,
    },
    {
        'ignite_version': '2.5.5',
        'help': help_2_5_1_and_higher,
        'commands': commands_2_5_1_and_higher_with_yes,
    },
    {
        'ignite_version': '2.5.8',
        'help': help_2_5_8_and_higher,
        'commands': commands_2_5_8_and_higher_with_yes,
    },
]

@pytest.mark.parametrize('data', testdata, ids=[test['ignite_version'] for test in testdata])

def test_parse_help(data):
    class MockIgnite:
        name = 'ignite'
    ignite = MockIgnite()
    cu = ControlUtility(ignite)
    ignite_version = data['ignite_version']

    help_file_path = os.path.join(
        os.path.dirname(__file__), 'res', 'control_utility', 'test_parse_help_%s.txt' % ignite_version
    )

    pp = PrettyPrinter()

    with open(help_file_path, 'r') as f:
        help_text = f.readlines()
        parsed_help = cu._ControlUtility__parse_help(help_text)
        pp.pprint(parsed_help)

        if ''.join(help_text).strip() == '':
            assert 0 == len(parsed_help)
            return

        assert len(data['help']) == len(parsed_help), "Help was parsed"

        for command_help in parsed_help.keys():
            command = cu._ControlUtility__parse_commands({command_help: parsed_help[command_help]})
            assert len(command) == 1, "Command understood"
            assert data['help'][command_help] in command.keys(), "Command parsed ok"

        commands = cu._ControlUtility__parse_commands(parsed_help)
        assert len(data['commands']) == len(commands), "All commands understood"

        assert set(data['commands'].keys()) == set(commands.keys()), "Commands matched"

        for command, use_force in data['commands'].items():
            assert use_force == commands[command]['force'], "Force argument matches"

