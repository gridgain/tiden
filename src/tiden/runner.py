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

import os.path

from glob import glob

from os import path, mkdir, listdir
from os.path import isdir, join, exists, basename
from re import search
from shutil import rmtree

import yaml

from .tidenexception import TidenException
from .util import log_print, print_red, cfg


def get_long_path_len(modules):
    """
    Find longest length of the test name by scanning found modules as text files.
    :param modules:
    :return:
    """
    long_path_len = 0
    for test_module in modules.keys():
        # methods = util.get_test_methods("suites.%s" % test_module)
        methods = get_test_methods(modules[test_module]['path'])
        methods.extend(['setup', 'teardown'])
        short_name = get_class_from_module(test_module[test_module.rfind('.') + 1:])
        for method_name in methods:
            if method_name.startswith('test') or method_name == 'setup' or method_name == 'teardown':
                cur_path = "%s.%s.%s ..." % (test_module, short_name, method_name)
                if len(cur_path) > long_path_len:
                    long_path_len = len(cur_path)
    if long_path_len > 0:
        long_path_len += 3
    return long_path_len


def set_configuration_options(cfg_options, config, configuration):
    from tiden.tidenfabric import TidenFabric
    for i, cfg_option in enumerate(cfg_options):
        config[cfg_option] = configuration[i]
    TidenFabric().setConfig(config)


def get_configuration_representation(cfg_options, configuration):
    cfg_representation = []
    for i, cfg_option in enumerate(cfg_options):
        if type(configuration[i]) == type(True):
            cfg_representation.append(cfg_option + '=' + str(configuration[i]).lower())
        elif type(configuration[i]) == type(0) or type(configuration[i]) == type(0.1):
            cfg_representation.append(cfg_option + '=' + str(configuration[i]))
        elif type(configuration[i]) == type(''):
            cfg_representation.append(cfg_option + '=' + configuration[i])
        else:
            cfg_representation.append(cfg_option + '=' + "'" + str(configuration[i]) + "'")
    return '(' + ', '.join(cfg_representation) + ')'


def get_actual_configuration(config, cfg_options):
    configuration = []
    for cfg_option in cfg_options:
        cfg_option_value = cfg(config, cfg_option)
        if cfg_option_value is None:
            raise TidenException(
                "Expected configuration option '%s' not set, please pass its value with --to arg!" % cfg_option)
        configuration.append(cfg_option_value)
    return configuration


def get_test_modules(config, collect_only=False):
    """
    Find test suite name and test cases (modules).
        config['suite_name'] must be set to the name of sub-directory in 'suites'
        config['test_name'] must be set to either name of test file (without extension) under suite directory or '*'
    :return: the dictionary of test case modules
        {
            '<suite_name>.<test_file_name>': {
                'path': <full-path-to-test-file>,
                'module_short_name': <test_file_name> without .py extension,
            }
        }

    """
    test_template = None
    test_cases = {}
    suite_name = config['suite_name']
    test_file = str(config['test_name'])
    if collect_only:
        for file_path in glob("suites/%s/%s.py" % (suite_name, test_file)):
            file = str(basename(file_path))
            if file.startswith('test') and file.endswith('.py'):
                actual_suite_name = basename(os.path.dirname(file_path))
                test_cases["%s.%s" % (actual_suite_name, file[:-3])] = {
                    'path': str(file_path).replace('\\', '/'),
                    'module_short_name': file[:-3]
                }
    else:
        # Check suite directory
        if not path.exists('suites/' + suite_name):
            print("Error: suite '%s' not found in suites" % suite_name)
            exit(1)
        # Check test case file
        if not path.exists('suites/' + suite_name + '/' + test_file + '.py') and '*' not in test_file:
            print("Error: test case file '%s' not found in %s" % (suite_name, test_file))
            exit(1)
        for file_path in glob("suites/%s/%s.py" % (suite_name, test_file)):
            file = str(basename(file_path))
            if file.startswith('test') and file.endswith('.py'):
                test_cases["%s.%s" % (suite_name, file[:-3])] = {
                    'path': str(file_path).replace('\\', '/'),
                    'module_short_name': file[:-3]
                }
    return test_cases


def get_class_from_module(module_name):
    """
    Construct test class name from name of module name by following rules:
     1. Capitalize the first character
     2. Capitalize the character follow after underscore character
     3. Remove underscore character
     e.g. test_super_module becomes TestSuperModule
    :param module_name: module name
    :return:            class name
    """
    class_name = ''
    idx = 0
    while idx < len(module_name):
        if module_name[idx:idx + 1] == '_':
            class_name += str(module_name[idx + 1:idx + 2]).capitalize()
            idx += 1
        else:
            class_name += module_name[idx:idx + 1]
            if idx == 0:
                class_name = class_name.capitalize()
        idx += 1
    return class_name


def get_test_methods(test_file_path):
    """
    Get test methods by scan python class file
    :param test_file_path:   full test path to python class file
    :return:            the list of test methods
    """
    methods = []
    with open(test_file_path) as f:
        lines = f.readlines()
    test_file_name_without_ext = '.'.join(basename(test_file_path).split('.')[:-1])
    class_name = get_class_from_module(test_file_name_without_ext)
    class_found = False
    for line in lines:
        m = search(' +def +(test_[a-z_A-Z0-9]+)', line)
        if class_found and m:
            methods.append(m.group(1))
        if line.startswith('class '):
            m = search('class +' + class_name, line)
            if m:
                class_found = True
            else:
                class_found = False
    return methods


def setup_test_environment(config):
    """
    Setup environment
    Creating artifact directories
    """

    if config['clean'] == 'all' and path.exists(config['var_dir']):
        log_print('Clean up {}'.format(config['var_dir']))
        rmtree(config['var_dir'])
    elif config['clean'] == 'tests' and path.exists(config['var_dir']):
        log_print('Clean up tests data in {}'.format(config['var_dir']))
        for item in listdir(config['var_dir']):
            item_path = join(config['var_dir'], item)
            if isdir(item_path):
                if search("^.+-.+?", item):
                    log_print(". {} dir deleted".format(basename(item_path)))
                    rmtree(item_path)

    if not exists(config['var_dir']):
        mkdir(config['var_dir'])

    # Make local suite directory
    suite_var_dir = "%s/%s" % (config['var_dir'], config['dir_prefix'])
    if not path.exists(suite_var_dir):
        mkdir(suite_var_dir)
    config['suite_var_dir'] = suite_var_dir

    # Make local artifacts directory
    artifacts_dir = "%s/artifacts" % config['var_dir']
    if not path.exists(artifacts_dir):
        mkdir(artifacts_dir)
    config['artifacts_dir'] = artifacts_dir
    tmp_dir = "%s/tmp" % suite_var_dir
    if not path.exists(tmp_dir):
        mkdir(tmp_dir)
    config['tmp_dir'] = tmp_dir

    # Ssh
    config['ssh'].update({
        'username': config['environment']['username'],
        'private_key_path': config['environment']['private_key_path'],
        'home': str(config['environment']['home']),
    })

    # Remote paths
    remote_suite_var_dir = "%s/%s" % (str(config['environment']['home']), config['dir_prefix'])
    config['remote'] = {
        'suite_var_dir': remote_suite_var_dir,
        'artifacts_dir': "%s/artifacts" % str(config['environment']['home'])
    }

    # Store config
    config['config_path'] = "%s/config.yaml" % config['suite_var_dir']
    with open(config['config_path'], 'w') as w:
        yaml.dump(config, w)

    return config


def init_remote_hosts(ssh_pool, config):
    # Print available disk space
    total_space, min_space = ssh_pool.available_space()
    log_print('Available space: total {} GB, min {}'.format(total_space, min_space),
              color='red' if isinstance(min_space, set) else 'info')

    # clean tests space
    if config['clean'] == 'all':
        clean_remote_path = '{}/*'.format(config['environment']['home'])
        log_print('Clean up {} on remote hosts'.format(clean_remote_path))
        cmd = 'rm -rvf {}'.format(clean_remote_path)
        ssh_pool.exec([cmd])
        total_space, min_space = ssh_pool.available_space()
        log_print('Available space after clean up: total {} GB, min {} GB'.format(total_space, min_space))
    elif config['clean'] == 'tests' or config['clean'] == 'remote_tests':
        log_print('Clean up tests data on remote hosts')
        cmd = "cd {} && ls | grep -E '^.+-.+?' | xargs rm -rf".format(config['environment']['home'])
        ssh_pool.exec([cmd])
        total_space, min_space = ssh_pool.available_space()
        log_print('Available space after clean up: total {} GB, min {} GB'.format(total_space, min_space))

    # Make suite remote directory
    for remote_dir in config['remote'].values():
        log_print('Make remote directory %s' % remote_dir)
        ssh_pool.exec(['mkdir -p %s' % remote_dir])


def skip_process_termination(ssh_pool, config):
    skip_termination, another_user_ps = False, False
    owner_processes = ssh_pool.get_process_and_owners()
    for details in owner_processes:
        if details.get('owner') and details.get('owner') != config['environment']['username']:
            print_red('Find process with PID: %s by user: %s on host: %s' %
                      (details.get('pid'), details.get('owner'), details.get('host')))
            another_user_ps = True
            if config.get('force_setup'):
                print_red('WARNING: Going to terminate processes from another user')
            else:
                skip_termination = True
    if skip_termination:
        print_red('Runner terminated: force_setup flag is not set. '
                  '(To kill all alien processes use --to=force_setup=True)')
    return skip_termination, another_user_ps


def upload_artifacts(ssh_pool, config, remote_unzip_files):
    """
    Upload artifacts.
    :param ssh_pool:
    :param config:
    :return:''
    """
    log_print("*** Deploy artifacts ***", color='blue')
    log_print('Preliminary file list for upload: %s' % ', '.join(listdir(config['artifacts_dir'])))
    log_print('Exclude already uploaded files')
    remote_artifacts = config['remote']['artifacts_dir']
    files = ssh_pool.not_uploaded(glob("%s/*" % config['artifacts_dir']), remote_artifacts)
    if len(files) > 0:
        log_print('Final file list for upload: %s' % ', '.join(files))
        ssh_pool.upload(files, remote_artifacts)
    else:
        log_print('Nothing found for upload')

    log_print('Remote unzip artifacts')
    ssh_pool.exec(remote_unzip_files)


def known_issue_str(know_issue):
    if know_issue:
        return " known issue found %s" % know_issue
    else:
        return ""

