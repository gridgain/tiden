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

from math import sqrt, floor
from optparse import OptionParser, SUPPRESS_USAGE
from os import cpu_count, getcwd
from os.path import abspath
import sys

from time import strftime

from tiden.tidenpluginmanager import PluginManager
from tiden import *
from tiden.artifacts import prepare
from tiden.logger import *
from tiden.runner import setup_test_environment, init_remote_hosts, upload_artifacts
from tiden.tidenfabric import TidenFabric
from tiden.tidenrunner import TidenRunner

from tiden.__version__ import __version__

version = 'Tiden ' + __version__

collect_only = False


class ConnectionMode(Enum):
    SSH = 'paramiko'
    LOCAL = 'local'
    ANSIBLE = 'ansible'


def create_parser():
    # Parse command-line arguments
    parser = OptionParser(usage=SUPPRESS_USAGE, add_help_option=False)
    parser.add_option("--ts", action='store', default=None)
    parser.add_option("--tc", action='append', default=[])
    parser.add_option("--var_dir", action='store', default=None)
    parser.add_option("--to", action='append', default=[])
    parser.add_option("--clean", action='store', default='')
    parser.add_option("--attr", action='append', default=[])
    parser.add_option("--collect-only", action='store_true', default=False)
    return parser


def process_args():
    global logger
    global collect_only
    config = {
        'environment': {
            'env_vars': {},
        },
        'ignite': {
            'bind_to_host': False,
            'unique_node_ports': False,
        },
        'attr_match': 'any',
        'ssh': {
            'default_timeout': SshPool.default_timeout
        },
        'xunit_file': 'xunit.xml',
        'artifacts_hash': 'artifacts_hash.yaml'
    }
    parser = get_option_parser()
    options, args = parser.parse_args()
    collect_only = options.collect_only

    # Read all YAML files in property 'config'
    yaml_files = options.tc

    # Apply 'default-plugins.yaml' and other config files by mask before applying options from configs passed via --tc
    for default in sorted(glob("config/default-*.yaml")):
        yaml_files.insert(0, default)

    for config_file in yaml_files:
        cur_data = read_yaml_file(config_file)
        if cur_data is None:
            log_print(f"Configuration file {config_file} is empty", color='red')
        for key_level_1 in cur_data.keys():
            if isinstance(cur_data[key_level_1], dict):
                if not config.get(key_level_1):
                    config[key_level_1] = {}
                for key_level_2 in cur_data[key_level_1]:
                    # if child dict contain _remove attribute then delete this child
                    if isinstance(cur_data[key_level_1][key_level_2], dict) \
                            and cur_data[key_level_1][key_level_2].get('_remove', False) \
                            and config[key_level_1].get(key_level_2):
                        del config[key_level_1][key_level_2]
                    else:
                        config[key_level_1][key_level_2] = cur_data[key_level_1][key_level_2]
            else:
                config[key_level_1] = cur_data[key_level_1]

    if len(options.tc) > 0:
        log_print(f"Read configuration from {', '.join(options.tc)}")
    else:
        log_print('No configurations found')
        exit(1)

    # Force property's config
    for force_arg in options.to:
        # Handle force_arg values such as "environment.server_jvm_options=-DIGNITE_QUIET=false"
        option_name, option_value = force_arg.split('=', 1)
        cfg(config, option_name, option_value)
        # self.logger.log("Configuration option %s=%s" % (option_name, option_value), 1)
    config['suite_name'] = None
    if options.ts is None:
        suite_mask = '*.*'
    else:
        suite_mask = options.ts
    if '.' in suite_mask:
        (config['suite_name'], config['test_name']) = suite_mask.split('.')
    else:
        config['suite_name'] = suite_mask
        config['test_name'] = '*'

    if '*' in config['suite_name'] and not collect_only:
        log_print('Single test session can run only one suite, please specify it with --ts option')
        exit(1)

    if collect_only:
        config['dir_prefix'] = f"collect-{strftime('%y%m%d-%H%M%S')}"
    else:
        config['dir_prefix'] = "{}-{}".format(config['suite_name'], strftime("%y%m%d-%H%M%S"))

    con_mode = config.get("connection_mode", "ssh")
    con_mode_found = [mode.value for mode in ConnectionMode if mode.name.lower() == con_mode]
    available_modes = '\nAvaliale modes:\n\t{}'.format('\n\t'.join([enum.name.lower() for enum in ConnectionMode]))
    assert con_mode_found, "Wrong connection mode selected '{}'{}".format(con_mode, available_modes)

    config["connection_mode"] = con_mode_found[0]
    config['clean'] = options.clean
    config['attrib'] = options.attr
    config['suite_dir'] = unix_path("%s/suites/%s" % (getcwd(), config['suite_name']))
    config['rt'] = {}
    config['var_dir'] = options.var_dir
    # Make var_dir
    if options.var_dir is None:
        config['var_dir'] = path.join(path.realpath(getcwd()), 'var')
    config['var_dir'] = unix_path(config['var_dir'])

    _fixup_hosts(config)
    return config


def _fixup_hosts(config):
    """
    Ensure that all existing xxx_hosts configuration options are really arrays of hosts.
    :param config:
    :return:
    """

    def _fixup_hosts_config_option(cfg, option_name):
        """
        fixup given xxx_hosts configuration option to be array of hosts
        :param cfg: config dict
        :param option_name: option name
        :return:
        """
        if not cfg.get(option_name):
            # ensure option is empty list when empty or not set
            cfg[option_name] = []
            return
        data = cfg[option_name]
        if isinstance(data, list):
            # remove empty items from list
            cfg[option_name] = [host for host in data if host]
            return
        # option seems to be string, clean it up, split by ','
        hosts = []
        data = str(data).replace(' ', '').strip(',')
        if data != '':
            hosts.extend([host for host in str(data).split(',') if host])
        cfg[option_name] = hosts.copy()

    # all options ended with '_hosts' but for 'apps_use_global_hosts' are considered hosts-like
    # e.g. environment.client_hosts, environment.server_hosts, environment.zk_hosts
    for name in config['environment'].keys():
        if name.endswith('_hosts') and not name == 'apps_use_global_hosts':
            _fixup_hosts_config_option(config['environment'], name)

    # all options ended with '_hosts' in all application configs also are hosts-like
    # (e.g. environment.mysql.server_hosts)
    for name, data in config['environment'].items():
        if isinstance(data, dict):
            for inner_name in data.keys():
                if inner_name.endswith('_hosts'):
                    _fixup_hosts_config_option(data, inner_name)


def _get_default_logger(config):
    """
    Generate logger with default settings

    :return: basic console tiden logger
    :rtype: TidenLogger
    """
    log_cfg = None
    if config.get('environment') and config['environment'].get('logger'):
        log_cfg = config['environment'].get('logger')

        if 'file_handler' in log_cfg.keys():
            log_file = '%s/%s' % (config.get('suite_var_dir'), log_cfg.get('file_handler').get('log_file', 'tiden.log'))
            log_cfg['file_handler']['log_file'] = log_file
    TidenLogger.set_logger_env_config(log_cfg)
    _log = TidenLogger('tiden')
    _log.set_suite('tiden-runner')
    return _log


def init_ssh_pool(config):
    log_print("*** Create SSH Pool ***", color='blue')
    # Collect unique hosts
    hosts = []
    for name, data in config['environment'].items():
        if name.endswith('_hosts') and not name == 'apps_use_global_hosts' and data is not None:
            hosts.extend(data)
    for name, data in config['environment'].items():
        if isinstance(data, dict):
            for inner_name, inner_data in data.items():
                if inner_name.endswith('_hosts'):
                    hosts.extend(inner_data)

    hosts = set(hosts)
    config['ssh']['hosts'] = list(hosts)
    # Calculate threads number
    config['ssh']['threads_num'] = floor(sqrt(len(hosts)))
    if config['ssh']['threads_num'] < cpu_count():
        config['ssh']['threads_num'] = cpu_count()

    if config['environment'].get('env_vars'):
        config['ssh']['env_vars'] = config['environment']['env_vars']
    write_yaml_file(config['config_path'], config)

    # Make SSH connection pool
    ssh_pool = None
    if 'ansible' == config['connection_mode']:
        try:
            from tiden.ansiblepool import AnsiblePool
            ssh_pool = AnsiblePool(config['ssh'])
        except ImportError as e:
            log_put('ERROR: unable to import AnsiblePool: %s' % e)
            exit(1)
    elif 'paramiko' == config['connection_mode']:
        ssh_pool = SshPool(config['ssh'])
    elif 'local' == config['connection_mode']:
        config['ignite']['bind_to_host'] = True
        config['ignite']['unique_node_ports'] = True
        try:
            from tiden.localpool import LocalPool
            ssh_pool = LocalPool(config['ssh'])
        except ImportError as e:
            log_put('ERROR: unable to import LocalPool: %s' % e)
            exit(1)
        except NotImplementedError as e:
            log_put('ERROR: %s' % e)
            exit(1)
    else:
        log_put("ERROR: Unknown 'connection_mode' %s" % config['connection_mode'])
        exit(1)

    if ssh_pool:
        TidenFabric().setSshPool(ssh_pool)
        ssh_pool.connect()
    return ssh_pool


def main():
    """
    Run Tiden tests
    """
    log_print("*** Initialization ***", color='blue')
    log_print('(c) 2017-{} GridGain Systems. All Rights Reserved'.format(max(datetime.now().year, 2019)))
    log_print(version)
    exit_code = None

    # parse arguments,
    # load configuration,
    # initialize working directories
    config = TidenFabric().setConfig(setup_test_environment(process_args())).obj
    log_print('The configuration stored in %s' % config['config_path'])

    logger = _get_default_logger(config)
    sys.path.insert(0, abspath(getcwd()))

    pm = PluginManager(config)

    # prepare artifacts, artifact information is updated into config
    # this must be done before tests collections,
    # because some tests are applicable for specific artifacts only
    log_print('*** Prepare artifacts ***', color='blue')
    pm.do('before_prepare_artifacts', config)
    remote_unzip_files, config = prepare(config)

    if collect_only:
        # we don't run any test, so no ssh pool nor plugin manager required
        ssh_pool = None
        pm = None
    else:
        # otherwise, create ssh pool,
        # and prepare plugins to use it
        ssh_pool = init_ssh_pool(config)
        if pm.plugins:
            log_print('*** Plugins ***', color='blue')
            for name, plugin in pm.plugins.items():
                log_print("%s, version %s" % (name, plugin['TIDEN_PLUGIN_VERSION']))
            pm.set(ssh=ssh_pool)

    # initialize tests runner
    log_print('*** Runner ***', color='blue')
    tr = TidenRunner(config, collect_only=collect_only, ssh_pool=ssh_pool, plugin_manager=pm)
    if len(tr.modules.keys()) == 0:
        log_print("Error: no test modules found")
        exit(1)
    log_print("%s module(s) matched %s.%s" % (len(tr.modules.keys()), config['suite_name'], config['test_name']))

    if collect_only:
        tr.collect_tests()
    else:
        pm.do('before_hosts_setup')
        init_remote_hosts(ssh_pool, config)

        pm.do('after_hosts_setup')
        upload_artifacts(ssh_pool, config, remote_unzip_files)

        if pm.do_check('before_tests_run'):
            tr.process_tests()
        else:
            exit_code = -1
        pm.do('after_tests_run')

    result = tr.get_tests_results()
    result.flush_xunit()
    result.print_summary()
    result.create_testrail_report(config, report_file=config.get('testrail_report'))

    print_blue("Execution time %d:%02d:%02d " % hms(int(time()) - result.get_started()))

    if exit_code:
        exit(exit_code)


if __name__ == '__main__':
    main()
