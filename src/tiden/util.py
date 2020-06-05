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

import functools
import warnings
import hashlib
import inspect

from yaml import load, YAMLError, dump, Loader, FullLoader
from datetime import datetime
from genericpath import exists
from time import sleep, time
from jinja2 import Environment, FileSystemLoader
from json import loads
from os import path, listdir
from inspect import stack
from sys import stdout
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from enum import Enum
from xml.etree.ElementTree import ElementTree, parse as _parse_xml
from .logger import get_logger
from re import search, sub
from glob import glob


def cfg(config, name, new_value=None):
    """
    Get a config value by name. If new value is set, then set the new value by a given name.
    :param config: A dictionary with test configuration.
    :param name: A key to the value. Several keys may be nested into one name, e.g. "environment.username"
    :param new_value: Set a config value if not None. Extend list in current value if new value starts with '+'.
    :return:
    """
    cur_val = get_nested_key(config, name)
    if new_value is None:
        if name.endswith('_enabled') and cur_val is None:
            return False
        return cur_val
    else:
        if isinstance(cur_val, list):
            if new_value.startswith('+'):
                # Extend list in current value
                yaml_val = f"[{','.join(cur_val)},{new_value[1:]}]"
            else:
                yaml_val = f"[{new_value}]"
        elif ',' in new_value:
            yaml_val = f"[{new_value}]"
        else:
            yaml_val = new_value
        # Use yaml parser
        set_nested_key(config, name, load(yaml_val, Loader=Loader))


def get_nested_key(d: dict, key_path: str):
    """
    Get a value from a dictionary using nested key names.
    :param d: A dictionary
    :param key_path: A path to a key. E.g., "environment.username"
    :return: value in key_path
    """
    keys = key_path.split('.')
    d0 = d
    while len(keys) > 1:
        d0 = d0.get(keys.pop(0), {})
    return d0.get(keys.pop(0))


def set_nested_key(d: dict, key_path: str, value):
    """
    Set a value in a dictionary using nested key names.
    :param d: A dictionary.
    :param key_path: A path to a key to set. E.g., "environment.username".
    :param value: A value to set.
    :return:
    """
    keys = key_path.split('.')
    d0 = d
    while len(keys) > 1:
        key = keys.pop(0)
        d0.setdefault(key, {})
        d0 = d0[key]
    d0[keys.pop(0)] = value


def read_yaml_file(file_path):
    """
    Read YAML file
    :param file_path:   path to YAML file
    :return:            dictionary or None for some cases
    """
    output = None
    try:
        with open(file_path, 'r') as file:
            output = load(file, Loader)
    except FileNotFoundError as e:
        print(str(e))
        print("Error: File '%s' not found" % file_path)
        exit(1)
    except YAMLError as e:
        print(str(e))
        print("Error: Can't read '%s' as YAML file" % file_path)
        exit(1)
    return output


def write_yaml_file(file_path, data):
    with open(file_path, 'w') as w:
        dump(data, w)


def call_method(cls, name):
    """
    Call class method by its name
    :param cls:     class instance
    :param name:    method name
    :return:        None
    """
    try:
        method = getattr(cls, name)
    except AttributeError:
        raise NotImplementedError("Class `{}` does not implement `{}`".format(cls.__class__.__name__, name))
    method()


def get_config_by_url(cfg, url):
    """

    :param cfg: dictionary
    :param url: path to value separated by dot, e.g, key1.key2.key3
    :return:    value from dictionary
    """
    keys = url.split('.')
    for key in keys:
        cfg = cfg[key]
    return cfg


def repeat_str(s, num):
    """
    Repeat string
    :param s:   string
    :param num: repeat number
    :return:    string
    """
    output = ''
    for i in range(0, num):
        output += s
    if len(output) > 0:
        output += ' '
    return output


def json_request(url, **kwargs):
    """
    Request JSON data by HTTP
    :param url: requested URL
    :return:    the dictionary
    """
    if 'auth_creds' in kwargs and 'authentication_enabled' in kwargs['auth_creds']:
        if 'sessionToken' in kwargs:
            url += "&sessionToken=%s" % kwargs['auth_creds']['sessionToken']
        else:
            url += "&ignite.login=%s&ignite.password=%s" % (kwargs['auth_creds']['auth_login'],
                                                            kwargs['auth_creds']['auth_password'])
    req = Request(url)
    decoded = {}
    try:
        r = urlopen(req)
        reply = r.read().decode('UTF-8')
        decoded = loads(reply)
    except HTTPError:
        print('')
        print("HTTPError %s" % url)
    except URLError:
        print('')
        print("URLError %s" % url)
    return decoded


def json_request_with_errors(url, **kwargs):
    """
    Request JSON data by HTTP
    :param url: requested URL
    :return:    the dictionary
    """
    if 'auth_creds' in kwargs and 'authentication_enabled' in kwargs['auth_creds']:
        if 'sessionToken' in kwargs:
            url += "&sessionToken=%s" % kwargs['auth_creds']['sessionToken']
        else:
            url += "&ignite.login=%s&ignite.password=%s" % (kwargs['auth_creds']['auth_login'],
                                                            kwargs['auth_creds']['auth_password'])
    req = Request(url)

    r = urlopen(req)
    reply = r.read().decode('UTF-8')
    decoded = loads(reply)

    return decoded


def hms(seconds):
    """
    Return time as hours, minutes seconds
    :param seconds: input seconds
    :return:        hours, minuted, seconds
    """
    mins, sec = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    return hours, mins, sec


def exec_time(n, mode=0):
    """
    Return special format for execution time
    :param n:       timestamp
    :param mode:    mode
    :return:    string in format [  NNN]
    """
    if mode == 0:
        return "[" + str(int(time() - n)).rjust(6) + "]"
    else:
        return int(time() - n)


def __is_called_from_line():
    data = stack()
    file_positions = []
    for item in data:
        if 'suites' in item[1]:
            file_positions.insert(0, f":{item[2]}")
    return file_positions


def log_add(msg, level=3, **kwargs):
    stdout.write(msg)
    stdout.flush()


def log_put(msg, level=3, **kwargs):
    line_nums = __is_called_from_line()
    prefix_str = ''
    if len(line_nums) > 0:
        line_num = "[%s]" % ' '.join(line_nums)
        prefix_str = '[%s]%s ' % (
            datetime.now().isoformat()[11:-7],
            line_num
        )
    stdout.write('\r%s%s' % (prefix_str, msg))
    stdout.flush()
    logger = get_logger('tiden')
    logger.info(msg)
    if kwargs.get('report'):
        from tiden.tidenfabric import TidenFabric
        result_lines_collector = TidenFabric().getResultLinesCollector()
        result_lines_collector.add_line(msg)


def log_print(msg=None, level=3, **kwargs):
    if msg is None:
        msg = ''
    fmt_str = '{}{}'
    colors = {'green': f'\033[32m{fmt_str}\033[0m',
              'red': f'\033[91m{fmt_str}\033[0m',
              'blue': f'\033[94m{fmt_str}\033[0m',
              'yellow': f'\033[93m{fmt_str}\033[0m',
              'pink': f'\033[95m{fmt_str}\033[0m',
              'bold': f'\033[1m{fmt_str}\033[0m',
              'debug': f'\033[35m{fmt_str}\033[0m'}

    prefix_str = ''
    if msg != '':
        line_nums = __is_called_from_line()
        if len(line_nums) > 0:
            line_num = "[{}]".format(' '.join(line_nums))
            prefix_str = '[{}]{} '.format(
                datetime.now().isoformat()[11:-7],
                line_num
            )
    if kwargs.get('color'):
        fmt_str = colors.get(kwargs.get('color'), fmt_str)
    if msg is not None:
        print(fmt_str.format(prefix_str, msg))
        logger = get_logger('tiden')
        logger.info(msg)
    else:
        # stdout.write('\n')
        # stdout.flush()
        logger = get_logger('tiden')
        logger.info('', skip_prefix=True)
    if kwargs.get('report'):
        from tiden.tidenfabric import TidenFabric
        result_lines_collector = TidenFabric().getResultLinesCollector()
        result_lines_collector.add_line(msg)


def skip(msg):
    def wrapper(func):
        func.__skipped__ = True
        func.__skipped_message__ = msg
        return func

    return wrapper


def version_num(version_text):
    """
    Convert text representation of version to number by format X.Y.Z to X0Y0Z
    For instance:
     1.2.3 -> 1020300
     1.2.3-p5 -> 1020305
    :param version_text:
    :return:
    """
    version_text = sub(r'(\.|\-)(b|t)\d+$', '', version_text)
    version_text = sub(r'-QA[A-Z]+\d+$', '', version_text)
    version_text = sub(r'\.final', '', version_text)
    version_text = sub(r'-SNAPSHOT', '', version_text)
    version_text = sub(r'-p', '.', version_text)
    ver_parts = version_text.split('.')
    if len(ver_parts) < 2:
        ver_parts.append('0')
    if len(ver_parts) < 3:
        ver_parts.append('0')
    if len(ver_parts) < 4:
        ver_parts.append('0')
    return 1000000 * int(ver_parts[0]) + 10000 * int(ver_parts[1]) + 100 * int(ver_parts[2]) + int(ver_parts[3])


def cond_all(f1, f2):
    def f(*args, **kwargs):
        res, msg = f1(*args, **kwargs)
        if not res:
            return (res, msg)
        return f2(*args, **kwargs)

    return f


def require_min_client_nodes(min_nodes):
    def cond_min_client_nodes(config):
        return (min_nodes <=
                len(config['environment']['client_hosts']) * int(config['environment'].get('clients_per_host', 1)),
                "Minimum client nodes must be %d" % min_nodes
                )

    def wrapper(func):
        if hasattr(func, '__skip_cond__'):
            func.__skip_cond__ = cond_all(func.__skip_cond__, cond_min_client_nodes)
        else:
            func.__skip_cond__ = cond_min_client_nodes
        return func

    return wrapper


def require_min_ignite_version(min_version):
    def cond_min_ignite_version(config):
        for artifact_name, artifact_data in config.get('artifacts', {}).items():
            if 'type' in artifact_data and artifact_data['type'] == 'ignite':
                ignite_version = version_num(artifact_data['ignite_version'])
                return (
                    ignite_version >= version_num(min_version),
                    "Ignite version < %s" % min_version
                )

        return False, 'No ignite artifacts found!'

    def wrapper(func):
        if hasattr(func, '__skip_cond__'):
            func.__skip_cond__ = cond_all(func.__skip_cond__, cond_min_ignite_version)
        else:
            func.__skip_cond__ = cond_min_ignite_version
        return func

    return wrapper


def require_min_server_nodes(min_nodes):
    def cond_min_server_nodes(config):
        return (min_nodes <=
                len(config['environment']['server_hosts']) * int(config['environment'].get('servers_per_host', 1)),
                "Minimum server nodes must be %d" % min_nodes
                )

    def wrapper(func):
        if hasattr(func, '__skip_cond__'):
            func.__skip_cond__ = cond_all(func.__skip_cond__, cond_min_server_nodes)
        else:
            func.__skip_cond__ = cond_min_server_nodes
        return func

    return wrapper


def require(*args, **kwargs):
    def get_check_min_server_nodes(min_nodes):
        def check_min_server_nodes(testcase):
            if 'servers_per_host' in testcase.config['environment']:
                servers_per_host = int(testcase.config['environment']['servers_per_host'])
            else:
                servers_per_host = 1
            return (min_nodes <=
                    len(testcase.config['environment']['server_hosts']) * servers_per_host,
                    "Minimum server nodes must be %d" % min_nodes
                    )

        return check_min_server_nodes

    def get_check_min_server_hosts(min_hosts):
        def check_min_server_hosts(testcase):
            return (min_hosts <=
                    len(testcase.config['environment']['server_hosts']),
                    "Minimum server hosts must be %d" % min_hosts
                    )

        return check_min_server_hosts

    def get_check_min_client_hosts(min_hosts):
        def check_min_client_hosts(testcase):
            return (min_hosts <=
                    len(testcase.config['environment']['client_hosts']),
                    "Minimum client hosts must be %d" % min_hosts
                    )

        return check_min_client_hosts

    def get_check_min_client_nodes(min_nodes):
        def check_min_client_nodes(testcase):
            if 'clients_per_host' in testcase.config['environment']:
                clients_per_host = int(testcase.config['environment']['clients_per_host'])
            else:
                clients_per_host = 1
            return (min_nodes <=
                    len(testcase.config['environment']['client_hosts']) * clients_per_host,
                    "Minimum client nodes must be %d" % min_nodes
                    )

        return check_min_client_nodes

    def get_check_min_zookeeper_nodes(min_zookeeper_nodes):
        def check_min_zookeeper_nodes(testcase):
            if 'zookeeper_per_host' in testcase.config['environment']:
                zookeeper_per_host = int(testcase.config['environment']['zookeeper_per_host'])
            else:
                zookeeper_per_host = 1
            return (min_zookeeper_nodes <=
                    len(testcase.config['environment'].get('zookeeper_hosts', [])) * zookeeper_per_host,
                    "Minimum client nodes must be %d" % min_zookeeper_nodes
                    )

        return check_min_zookeeper_nodes

    def get_check_min_zookeeper_hosts(min_hosts):
        def check_min_zookeeper_hosts(testcase):
            return (min_hosts <=
                    len(testcase.config['environment'].get('zookeeper_hosts', [])),
                    "Minimum Zookeeper server hosts must be %d" % min_hosts
                    )

        return check_min_zookeeper_hosts

    def get_check_min_ignite_version(min_ignite_version):
        def check_min_ignite_version(testcase):
            for artifact_name, artifact_data in testcase.config.get('artifacts', {}).items():
                if 'type' in artifact_data and artifact_data['type'] == 'ignite':
                    ignite_version = version_num(artifact_data['ignite_version'])
                    return (
                        ignite_version >= version_num(min_ignite_version),
                        "Ignite version < %s" % min_ignite_version
                    )
            return False, "No Ignite artifacts found"

        return check_min_ignite_version

    def get_option_checker(arg, argname):
        def check_option(testcase):
            return (arg, argname)

        return check_option

    def getAttrObj_checker(attr_obj):
        def check_attr_obj(testcase):
            from tiden.testconfig import test_config
            is_negated = attr_obj.__negated__
            argname = attr_obj.__name__()
            option_name = argname.split('.')[1:]

            # extract run time value with the same name as original attribute from actual test_config
            arg = test_config
            for option in option_name:
                arg = arg.__getattr__(option)

            if arg is None:
                # should not really be there
                msg = "%s is None" % argname
            elif hasattr(arg, 'value') and arg.value is None:
                if is_negated:
                    msg = "%s is not None" % argname
                    arg = ~arg
                else:
                    msg = "%s is None" % argname
            elif hasattr(arg, '__negated__') and is_negated:
                msg = "%s is True" % argname[4:]
                arg = ~arg
            elif not arg:
                msg = "%s is False" % argname
            else:
                msg = "%s" % argname

            return (arg, msg)
        return check_attr_obj

    # import inspect
    def wrapper(func):
        if not hasattr(func, '__skip_conds__'):
            func.__skip_conds__ = []
        for condition_name, arguments in kwargs.items():
            if type(arguments) != type(list):
                arguments = [arguments]
            if condition_name == 'min_server_nodes':
                func.__skip_conds__.append(get_check_min_server_nodes(*arguments))
            if condition_name == 'min_server_hosts':
                func.__skip_conds__.append(get_check_min_server_hosts(*arguments))
            if condition_name == 'min_client_hosts':
                func.__skip_conds__.append(get_check_min_client_hosts(*arguments))
            if condition_name == 'min_zookeeper_node':
                func.__skip_conds__.append(get_check_min_zookeeper_nodes(*arguments))
            if condition_name == 'min_zookeeper_hosts':
                func.__skip_conds__.append(get_check_min_zookeeper_hosts(*arguments))
            if condition_name == 'min_client_nodes':
                func.__skip_conds__.append(get_check_min_client_nodes(*arguments))
            elif condition_name == 'min_ignite_version':
                func.__skip_conds__.append(get_check_min_ignite_version(*arguments))

        if len(args) > 0:
            for arg in args:
                if hasattr(arg, '__parent__'):
                    argname = arg.__name__()
                    func.__skip_conds__.append(getAttrObj_checker(arg))
                else:
                    _fr = inspect.currentframe()
                    _out_fr = inspect.getouterframes(_fr)
                    # msg = "expression evaluates to False at %s:%s" % (os.path.basename(_out_fr[1][1]), _out_fr[1][2])
                    msg = "expression evaluates to False at %s:%s" % (_out_fr[1][1], _out_fr[1][2])
                    func.__skip_conds__.append(get_option_checker(arg, msg))

        return func

    return wrapper


def unix_path(p):
    return p.replace('\\', '/')


def with_setup(*args, **kwargs):
    def wrapper(func):
        if len(args) >= 1:
            if type(args[0]) == type(''):
                func.__setup__ = args[0]
            else:
                if kwargs:
                    def wrapper2(self):
                        return args[0](self, **kwargs)
                    arg_str = '(' + ', '.join([k + '=' + str(v) for k, v in kwargs.items()]) + ')'
                    wrapper2.__name__ = args[0].__name__ + arg_str
                    func.__setup__ = wrapper2
                else:
                    func.__setup__ = args[0]
        if len(args) >= 2:
            if type(args[1]) == type(''):
                func.__teardown__ = args[1]
            else:
                func.__teardown__ = args[1].__name__
        return func
    return wrapper


def repeated_test(*args, **kwargs):
    def wrapper(func):
        if len(args) >= 1:
            func.repeated_test_count = args[0]
            func.repeated_test_name = kwargs.get('test_names', [])
            if len(func.repeated_test_name) < func.repeated_test_count:
                func.repeated_test_name.extend(
                    list(range(len(func.repeated_test_name) + 1, func.repeated_test_count + 1)))
        return func
    return wrapper


def attr(*args):
    def wrapper(func):
        func.__attrib__ = list(args)
        return func

    return wrapper


def known_issue(*args):
    def wrapper(func):
        func.__known_issues__ = list(args)
        return func

    return wrapper


def test_case_id(*args):
    def wrapper(func):
        if len(args) == 1 and args[0] == -1:
            return func
        func.__test_id__ = list(args)
        return func

    return wrapper


def should_be_skipped(passed_attr, attribs, attr_match, debug=False):
    skip_it = False
    if debug:
        print('------ Passed attributes --------')
        print(passed_attr)
        print('------ Attributes on test method --------')
        print(attribs)
    if passed_attr:
        if attribs:
            if attr_match == 'any':
                if isinstance(passed_attr, str):
                    if passed_attr not in attribs:
                        skip_it = True
                elif isinstance(passed_attr, list):
                    if not set(passed_attr).intersection(attribs):
                        skip_it = True
            elif attr_match == 'all':
                if isinstance(passed_attr, str):
                    if passed_attr not in attribs:
                        skip_it = True
                elif isinstance(passed_attr, list):
                    if not set(passed_attr).issubset(set(attribs)):
                        skip_it = True
            elif attr_match == 'not':
                if isinstance(passed_attr, str):
                    if passed_attr in attribs:
                        skip_it = True
                elif isinstance(passed_attr, list):
                    if any([attribute for attribute in attribs if attribute in passed_attr]):
                        skip_it = True

        else:
            skip_it = True
    if debug:
        print('Should be skipped: %s ' % skip_it)
    return skip_it


def print_green(msg):
    print('\033[92m' + str(msg) + '\033[0m')


def print_blue(msg):
    print('\033[94m' + str(msg) + '\033[0m')


def print_warning(msg):
    print('\033[93m' + str(msg) + '\033[0m')


def print_red(msg):
    print('\033[91m' + str(msg) + '\033[0m')


def print_debug(msg):
    print('\033[35m' + str(msg) + '\033[0m')


def print_fails(failed_tests):
    for test in failed_tests.keys():
        print_red('-------------------------------------------')
        print_red('Test %s failed with error:' % test)
        print_red('-------------------------------------------')
        print_red('%s' % failed_tests[test])


def human_size(s):
    terms = [
        'byte(s)', 'KB', 'MB', 'GB', 'TB'
    ]
    term_idx = 0
    while s > 1024:
        s /= 1024
        term_idx += 1
    return "%.2f %s" % (s, terms[term_idx])


def apply_tiden_functions(input_string, **kwargs):
    output_string = '%s' % input_string
    for key in kwargs.keys():
        if '${tiden.%s}' % key in output_string:
            output_string = output_string.replace('${tiden.%s}' % key, kwargs[key])
    return output_string


def util_sleep(period):
    log_print('Sleep %d sec ...' % period, color='blue')
    sleep(period)


def util_sleep_for_a_while(period, msg=''):
    log_print(f'sleep {period} sec. {msg} started at {datetime.now().strftime("%H:%M %B %d")}')
    started = int(time())
    timeout_counter = 0
    step = 3 if period > 3 else period
    while timeout_counter < period:
        log_put(f"timeout {timeout_counter}/{period} sec")
        stdout.flush()
        sleep(int(step))
        timeout_counter = int(time()) - started
    log_print()


def get_host_list(*lists):
    if len(lists) > 0:
        hosts = set(lists[0])

        for i in range(1, len(lists)):
            if lists[i]:
                hosts = hosts.union(lists[i])

        return hosts
    else:
        print_red("Empty lists!")


def is_enabled(param):
    return param in ['TRUE', 'True', 'true', True]


def md5_for_filename(filename):
    with open(filename, 'rb') as f:
        return md5_for_file(f)


def md5_for_file(f, block_size=2 ** 20):
    md5 = hashlib.md5()
    while True:
        data = f.read(block_size)
        if not data:
            break
        md5.update(data)
    return md5.digest()


def render_template(glob_path, name, options):
    output = {}
    output_dir = path.dirname(glob_path)
    for tmpl_file in glob(glob_path):
        file_parts = tmpl_file.split('.tmpl.')
        if len(file_parts) > 1:
            cfg_name = path.basename(file_parts[0])
            env = Environment(loader=FileSystemLoader(output_dir), trim_blocks=True)
            rendered_string = env.get_template(path.basename(tmpl_file)).render(options)
            cfg_path = "%s/%s" % (
                output_dir, path.basename(tmpl_file).replace('.tmpl.', '.%s.' % name))
            with open(cfg_path, "w+") as config_file:
                config_file.write(rendered_string)
                output[cfg_name] = path.basename(cfg_path)
    return output


def deprecated(func):
    """
    This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    """

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        warnings.simplefilter('always', DeprecationWarning)
        warnings.warn("Call to deprecated function {}.".format(func.__name__),
                      category=DeprecationWarning,
                      stacklevel=2)
        warnings.simplefilter('default', DeprecationWarning)
        return func(*args, **kwargs)

    return wrapped


def echo(func):
    """
    Returns a traced version of the input function.
    """
    from itertools import chain

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        name = func.__name__
        print("%s(%s)" % (
            name, ", ".join(map(repr, chain(args, kwargs.values())))))
        return func(*args, **kwargs)

    return wrapped


def calculate_sha256(file):
    import hashlib

    def hash_bytestr_iter(bytesiter, hasher, ashexstr=False):
        for block in bytesiter:
            hasher.update(block)
        return (hasher.hexdigest() if ashexstr else hasher.digest())

    def file_as_blockiter(afile, blocksize=65536):
        with afile:
            block = afile.read(blocksize)
            while len(block) > 0:
                yield block
                block = afile.read(blocksize)

    stream = open(file, 'rb')
    block_iter = file_as_blockiter(stream)
    bytes_hash = hash_bytestr_iter(block_iter, hashlib.sha256())
    return str(bytes_hash)


def current_time_millis():
    return int(round(time() * 1000))


def create_case(case):
    """
    Tests description annotation

    How to use:
        - set annotation for each test case which need to add into testrail
        - run tests with run-tests.py or nosetests [run attrs] --collect (without running)
        after testrun will be created file attr.yaml in tests directory needed for testrail case creation
    """
    from os.path import dirname
    from yaml import load, dump

    test_file_name = dirname(case.__globals__["__file__"])
    attr_yaml_path = '{}/attr.yaml'.format(test_file_name)
    try:
        existed_yaml = load(open(attr_yaml_path, 'r'), Loader=FullLoader) or {}
    except FileNotFoundError:
        existed_yaml = {}
    test_description = {}
    section_name = case.__module__
    case_name = case.__name__
    test_description["name"] = case_name
    if hasattr(case, '__test_id__'):
        test_id = getattr(case, '__test_id__')
        if type(test_id) == type([]):
            if len(test_id) == 1:
                test_id = test_id[0]
        if type(test_id) == type(''):
            try:
                int_test_id = int(test_id)
            except ValueError:
                pass
            except TypeError:
                pass
            else:
                if str(int_test_id) == test_id:
                    test_id = int_test_id
        test_description['test_case_id'] = test_id
    if case.__doc__ is not None:
        test_description["doc"] = case.__doc__
    if existed_yaml.get(section_name, False):
        # extend existed case if found difference
        for test_case in existed_yaml[section_name]:
            if test_case.get("name") == test_description["name"]:
                for key, value in test_case.items():
                    test_description[key] = test_description.get(key, value)
                break
        existed_yaml[section_name].append(test_description)
    else:
        existed_yaml[section_name] = [test_description]
    dump(existed_yaml, open(attr_yaml_path, 'w+'))
    return case


def make_number(s):
    val = s
    try:
        int_val = int(s)
        if str(int_val) == s:
            val = int_val
    except ValueError:
        pass
    except TypeError:
        pass

    try:
        float_val = float(s)
        if str(float_val) == s:
            val = float_val
    except ValueError:
        pass
    except TypeError:
        pass

    return val


def print_obj(obj):
    def get_message(item, addition='\t'):
        message = ''
        if isinstance(item, dict):
            message += '\n' + addition + '{'
            for k, v in item.items():
                message += '\n' + addition + '\t' + "{}: {}".format(k, get_message(v, addition=addition + '\t'))
            message += '\n' + addition + '}'
            return message
        elif isinstance(item, list):
            message += '\n' + addition + '['
            for i in item:
                message += '\n' + addition + '\t' + get_message(i)
            message += '\n' + addition + ']'
            return message
        else:
            return str(item)

    log_print(get_message(obj))


def parse_xml(path):
    """
    Parse xml file to dict
    File:
        <source-tag property_1="value_1" property_2="value_2">
            <inner-tag property_3="value_3"/>
            <inner-tag property_4="value_4"/>
        </source-tag>
    Result:
        [
            {
                "property_1": "value_1",
                "property_2": "value_2",
                "_tag": "source-tag"
                "_children": [
                                {
                                    "property_3": "value_3",
                                    "_children": [],
                                    "_tag": "inner-tag"
                                },
                                {
                                    "property_4": "value_4",
                                    "_children": [],
                                    "_tag": "inner-tag"
                                }
                            ]
            ]
        ]
    :param path:    file path
    :return:        parsed xml
    """

    def get_children(element):
        if isinstance(element, ElementTree):
            element = element.getroot()
        children = []
        for child in element.getchildren():
            item = {}
            grand_children = get_children(child)
            if child.attrib:
                item.update(child.attrib)
            item["_children"] = grand_children
            tag = child.tag
            # in common it's look like {http://www.springframework.org/schema/beans}tag-name
            item["_tag"] = tag[tag.rindex("}") + 1:] if '}' in tag else tag
            children.append(item)
        return children

    tree = _parse_xml(open(path, 'r'))
    return get_children(tree)


def merge_properties(previous_val, next_val):
    """
    Function used in reduce for merging several xml properties to dict
    Example:
        Source: [
                    {"name": "name", "value": "cache_name"},
                    {"name": "groupName", "value": "group_name"}
                ]
        Result: {
                    "name": "cache_name",
                    "groupName": "group_name"
                }
    :param previous_val:    reduce previous value
    :param next_val:        next value
    :return:                properties dict
    """
    if previous_val["name"] == 'name':
        previous_val["name"] = previous_val["value"]
        del previous_val["value"]
    previous_val[next_val["name"]] = next_val.get("value", next_val["_children"])
    return previous_val


def dict2str(d):
    """
    convert dict to str in order of keys
    :param d:
    :return: s
    """
    return '{' + ', '.join([str({k: d[k]})[1:-1] for k in sorted(d)]) + '}'


def encode_enums(obj):
    """
    Encode enums in yaml parser friendly data type
    :param obj:     object to encode
    :return:        encoded object
    """
    if isinstance(obj, dict):
        new_obj = {}
        for key, value in obj.items():
            value = encode_enums(value)
            new_obj[key] = value
        return new_obj
    elif isinstance(obj, Enum):
        return ['enum', type(obj).__name__, obj.name]
    else:
        return obj


def decode_enums(obj, available_enums=None):
    """
    Decode enums from parsed yaml file
    :param obj:             object to check
    :param available_enums  list of available enums classes to decode
    :return:                decoded object
    """

    if isinstance(obj, dict):
        new_obj = {}
        for key, value in obj.items():
            value = decode_enums(value, available_enums=available_enums)
            new_obj[key] = value
        return new_obj
    elif isinstance(obj, list):
        if len(obj) == 3 and obj[0] == 'enum':
            if available_enums:
                for enum in available_enums:
                    if enum.__name__ == obj[1]:
                        for enum_item in enum:
                            if enum_item.name == obj[2]:
                                return enum_item
        return obj
    else:
        return obj


def get_cur_timestamp():
    return datetime.now().isoformat()[11:-7]


def get_from_version_dict(version_dict, version):
    """
    Returns value from versioned dict. If exact version is not found in dict, then value for nearest version
    which is less than current will be returned.
    For example:
    version_dict = {'0': 'some_value', '2.5.1-p160': 'another values'}
    for version 2.5.1-p150 will be returned value for '0' key;
    for version 2.5.1-p161 will be returned value for '2.5.1-p160' key.

    :param version_dict:
    :param version:
    :return:
    """
    exact_value = version_dict.get(version)
    if not exact_value:
        exact_value = version_dict.get(util_get_nearest_version(version_dict, version))
    return  exact_value


def util_get_nearest_version(version_dict, version):
    ver_mapping = {}
    versions_to_check = []
    for ver in version_dict.keys():
        converted_version = version_num(ver)
        ver_mapping[converted_version] = ver
        versions_to_check.append(converted_version)

    versions_to_check.sort()
    exact_version = [ver for ver in versions_to_check if ver < version_num(version)][-1]
    return ver_mapping[exact_version]


def load_yaml(yaml_path):
    data = {}
    if exists(yaml_path):
        with open(yaml_path, 'r') as f:
            data = load(f, Loader)
    return data


def save_yaml(yaml_path, data):
    with open(yaml_path, 'w') as w:
         dump(data, stream=w, line_break=True, default_flow_style=False)


def camelcase(s):
    return sub(r'\w+', lambda m: m.group(0).capitalize(), s)


def from_camelcase(s):
    """
    convert camel case to underscore
    :param s: ThisIsCamelCase
    :return: this_is_camel_case
    """
    return ''.join(['_' + c.lower() if c.isupper() else c for c in s]).lstrip('_')


def versioned_files(*args, **kwargs):
    """
    Build a set of files matching for range of ignite version from major to given.
    E.g. for given ignite version '2.3.1', all existing files from '2.0.0' to '2.3.1' will be returned.
    :param args:
        args[0] - ignite version string, e.g. '2.3.1'
        args[1] - file mask, 'my.*.file', or a list of masks
        args[2] - base directory to search for files in
    :return: dictionary of files, indexed by ignite version number, e.g.
          { 2000000: '/my.2.file',
            2030000: '/my.2.3.file' }
    """
    high_ver_num = version_num(args[0])  # convert version string '2.3.1' to number, e.g.  2030100
    low_ver_num = 1000000 * int(args[0][0:1])  # get major version number, e.g. for '2.3.1'      2000000
    if isinstance(args[1], list):
        glob_mask = args[1]
    elif isinstance(args[1], str):
        glob_mask = [args[1]]
    directories = []
    if isinstance(args[2], list):
        directories = args[2]
    elif isinstance(args[2], str):
        directories.append(args[2])
    files = {}
    for directory in directories:
        for file_glob in glob_mask:
            for file in glob("%s/%s" % (directory, file_glob)):
                m = search(r'[a-z]+\.([0-9\.]+)\.[a-z]+', file)
                if m:
                    cur_ver_num = version_num(m.group(1))
                    if high_ver_num >= cur_ver_num >= low_ver_num:
                        if cur_ver_num in files:
                            if isinstance(files[cur_ver_num], list):
                                files[cur_ver_num].append(file)
                            else:
                                files[cur_ver_num] = [files[cur_ver_num], file]
                        else:
                            files[cur_ver_num] = file
    if 'debug_print_file_names' in kwargs:
        for files_per_version in files.values():
            if not isinstance(files_per_version, list):
                files_per_version = [files_per_version]
            for file in files_per_version:
                print('Versioned file: %s' % file)
    return files


def versioned_yaml(*args, **kwargs):
    """
    Make the dictionary by merging YAML dictionaries from oldest ot newest version
    :param args:
        args[0] - ignite version string, e.g. '2.3.1'
        args[1] - YAML file glob mask, e.g. 'conf.*.yaml', or a list of masks
        args[2] - base directory to search for YAML files in
    :return:
    """
    yaml_files = versioned_files(args[0], args[1], args[2], **kwargs)
    data = {}
    for yaml_key in sorted(yaml_files.keys()):
        yaml_file = yaml_files[yaml_key]
        if type(yaml_file) == type([]):
            yaml_file_list = yaml_file
        else:
            yaml_file_list = [yaml_file]
        for yaml_file in yaml_file_list:
            with open(yaml_file) as r:
                try:
                    cur = load(r)
                    if len(data) == 0:
                        data = dict(cur)
                    else:
                        for key in cur.keys():
                            if data.get(key) is None:
                                if not (isinstance(cur[key], dict) and
                                        cur[key].get('_action') is not None and
                                        cur[key]['_action'] == 'delete'):
                                    data[key] = cur[key]
                            else:
                                if isinstance(cur[key], dict):
                                    if cur[key].get('_action') is not None:
                                        if cur[key]['_action'] == 'delete':
                                            del data[key]
                                    else:
                                        for subkey in cur[key]:
                                            data[key][subkey] = cur[key][subkey]
                                elif isinstance(cur[key], list):
                                    data[key] = cur[key]
                except YAMLError as e:
                    print('versioned_yaml(\'%s\',%s,%s) had found YAMLError loading file \'%s\'\n%s' % (
                        args[0], args[1], args[2], yaml_file, str(e)))

                except TypeError as e:
                    print('versioned_yaml(\'%s\',%s,%s) had found TypeError loading file \'%s\'\n%s' % (
                        args[0], args[1], args[2], yaml_file, str(e)))
                    raise e
    # Set default options
    if data.get('_default'):
        default_options = data['_default'].copy()
        for key in data.keys():
            for default_key in default_options.keys():
                if data[key].get(default_key) is None:
                    data[key][default_key] = default_options[default_key].copy()
        del data['_default']
    return data


def version_dir(*args):
    """
    Search through a group of directories specified by list of base paths and prefix.
    Return (configuration) directory best matching to specified ignite version.
    :param args:
        args[0] - ignite version, string, e.g. '2.3.1'
        args[1] - directory prefix, string, e.g. 'attr'
        args[2] - directory paths, list, e.g. ['base', 'extend']
    :return: None, if did not found any match, otherwise, one of ['base/attr.2', 'base/attr.2.3', ... ]
    """
    high_ver_num = version_num(args[0])  # convert version string '2.3.1' to version num.       e.g. 2030100
    low_ver_num = 1000000 * int(args[0][0:1])  # convert major part of version string to version num. e.g. 2000000
    dir_prefix = args[1]
    dir_paths = args[2]
    latest_matched_version = low_ver_num
    latest_matched_path = None
    for dir_path in dir_paths:
        for subdir in listdir(dir_path):
            if subdir.startswith(dir_prefix):
                m = search(r'\.([0-9\.]+)$', subdir)
                if m:
                    cur_ver_num = version_num(m.group(1))  # convert version
                    if high_ver_num >= cur_ver_num >= low_ver_num:
                        if latest_matched_version <= cur_ver_num:
                            latest_matched_version = cur_ver_num
                            latest_matched_path = "%s/%s" % (dir_path, subdir)
    return latest_matched_path


def normpath(file):
    return path.normpath(path.abspath(file))


def prettydict(d):
    opts = {
        'default_flow_style': False,
        'indent': 4,
        'line_break': True,
    }
    return dump({'=>': d}, **opts)


def disable_connections_between_hosts(ssh, to_hosts, on_host):
    """
    disable connection by iptables rule between two hosts
    :param ssh: ssh pool
    :param to_hosts: hosts for disable
    :param on_host: host for run iptables command
    """
    if to_hosts == on_host:
        log_print(to_hosts != on_host, 'expect to_hosts: {} and on_host: {} diff'.format(to_hosts, on_host),
                  color='red')
    log_print('Add iptables rules for disable connections on host: %s' % to_hosts, color='red')
    cmd = []
    if isinstance(to_hosts, list):
        for host in set(to_hosts):
            cmd += _iptables_rule(host)
    else:
        cmd = _iptables_rule(to_hosts)

    results = ssh.exec_on_host(on_host, cmd)
    log_print(results)


def enable_connections_between_hosts(ssh, to_hosts, on_host):
    """
    enable connection by iptables rule between two hosts
    :param ssh: ssh pool
    :param to_hosts: hosts for disable
    :param on_host: host for run iptables command
    """
    if to_hosts == on_host:
        log_print(to_hosts != on_host, 'expect to_hosts: {} and on_host: {} diff'.format(to_hosts, on_host),
                  color='red')
    log_print('Drop iptables rules for enable connections on host: %s' % to_hosts, color='red')
    cmd = []
    if isinstance(to_hosts, list):
        for host in set(to_hosts):
            cmd += _iptables_rule(host, add_rule=False)
    else:
        cmd = _iptables_rule(to_hosts, add_rule=False)
    print_red(cmd)
    results = ssh.exec_on_host(on_host, cmd)
    log_print(results)


def _iptables_rule(host, add_rule=True):
    if add_rule:
        cmd = [
            'sudo iptables -w -A INPUT -s %s -j DROP' % host,
            'sudo iptables -w -A OUTPUT -d %s -j DROP' % host]
    else:
        cmd = [
            'sudo iptables -w -D INPUT -s %s -j DROP' % host,
            'sudo iptables -w -D OUTPUT -d %s -j DROP' % host
        ]
    return cmd


def if_applicable_ignite_version(config, min_version):
    for artifact_name, artifact_data in config.get('artifacts', {}).items():
        if 'type' in artifact_data and artifact_data['type'] == 'ignite':
            ignite_version = version_num(artifact_data['ignite_version'])

            if isinstance(min_version, str):
                return ignite_version >= version_num(min_version)
            elif isinstance(min_version, dict):
                for base_ver, min_bs_version in min_version.items():
                    if base_ver == artifact_data['ignite_version'][:3]:
                        return ignite_version >= version_num(min_bs_version)
    return False


def util_get_now():
    return datetime.now().strftime("%H:%M %B %d")


def kill_stalled_java(ssh):
    java_processes = ssh.jps()
    if java_processes:
        log_print('Found stalled java processes {}'.format(java_processes), color='debug')
        ssh.killall('java')
        sleep(3)
        java_processes = ssh.jps()

        if java_processes:
            log_print('Could not kill java processes {}'.format(java_processes), color='red')
        else:
            log_print('Killed stalled java processes', color='debug')


def get_jvm_options(dictionary, key):
    config_jvm_options = []
    if dictionary.get(key):
        if type(dictionary[key]) == type(str):
            config_jvm_options = [dictionary[key].split(' ')]
        else:
            config_jvm_options = list(dictionary[key])
    return config_jvm_options


def mergedict(source, destination):
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            mergedict(value, node)
        else:
            destination[key] = value

    return destination
