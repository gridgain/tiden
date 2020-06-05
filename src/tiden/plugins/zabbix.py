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

from tiden.tidenplugin import TidenPlugin, TidenPluginException
from tiden.zabbix_api import ZabbixApi
from tiden.util import get_host_list, print_red

from datetime import datetime

TIDEN_PLUGIN_VERSION = '1.0.0'


class ZabbixException(TidenPluginException):
    pass


class Zabbix(TidenPlugin):
    plot_config = {
        'Available memory':
            {
                'ylim': [0, 100161223168],
                'ylabel': 'RAM',
                'format': lambda x, pos: '%.1f G' % (x / (1000 * 1000 * 1000))
            },
        'The time the CPU has spent doing nothing':
            {
                'ylim': [0, 100],
                'ylabel': 'CPU',
                'format': lambda x, pos: '%.1f %%' % (x)
            },

    }
    zabbix_api = None
    start_time = None
    metrics = None
    create_plot = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        check_msg = 'Please check plugin configuration.'

        # Check that plugin configuration contains all it needs
        if not self.options:
            raise ZabbixException('zabbix plugin section is not found in configuration. %s' % check_msg)

        if self.options.get('url') and self.options.get('login') and self.options.get('password'):
            self.url = self.options.get('url')
            self.login = self.options.get('login')
            self.passwd = self.options.get('password')
            self.zabbix_api = ZabbixApi(self.url, self.login, self.passwd)
        else:
            raise ZabbixException('Zabbix credentials have not found in zabbix plugin configuration. %s' % check_msg)

        self.metrics = self.options.get('metrics', [])
        if self.metrics and len(self.metrics) == 0:
            raise ZabbixException('List metrics is empty in zabbix plugin configuration. %s' % check_msg)

        self.create_plot = self.options.get('create_plot', False)

    def after_test_method_setup(self, *args, **kwargs):
        """
        Just remember current time.
        :param args:
        :param kwargs:
        :return:
        """
        self.start_time = datetime.now()
        # self.start_time = datetime.datetime.now() - datetime.timedelta(minutes=60)

    def before_test_method_teardown(self, *args, **kwargs):
        """
        Fix current time and try to collect metrics.
        :param args:
        :param kwargs:
        :return:
        """
        stop_time = datetime.now()
        self.collect_metrics(self.start_time, stop_time)

    def collect_metrics(self, start_time, end_time):
        # TODO: replace this with method that knows all hosts
        hosts = get_host_list(self.config['environment']['server_hosts'],
                              self.config['environment']['client_hosts'],
                              self.config['environment'].get('coordinator_host', []))

        data = self.zabbix_api.collect_metrics_from_servers(hosts, self.metrics, start_time, stop_time=end_time)

        test_name = ''
        if self.config['rt']['remote'].get('test_dir'):
            test_name = self.config['rt']['remote'].get('test_dir').split('/')[-1]

        if self.create_plot:
            # if we can't import matplotlib don't fail the tests
            try:
                self.create_simple_plot(data, self.config['suite_var_dir'],
                                        plot_config=self.plot_config, extend_name=test_name)
            except ImportError:
                print_red('Error: matplotlib module could not be imported. Result will be save into text file.')
                self.write_result_to_file(data, self.config['suite_var_dir'], extend_name=test_name)
        else:
            self.write_result_to_file(data, self.config['suite_var_dir'], extend_name=test_name)

    @staticmethod
    def write_result_to_file(data, plot_path, extend_name=None):
        for metric_name, metric_data in data.items():
            for server in metric_data.keys():
                values = metric_data[server]['values']
                if len(metric_data[server]['timestamp']) != len(metric_data[server]['values']):
                    values = metric_data[server]['values'][0:(len(metric_data[server]['timestamp']))]

                file_name = '%s/zabbix-%s.txt' % (plot_path, metric_name.replace(' ', '_'))
                if extend_name:
                    file_name = '%s/zabbix-%s_%s.txt' % (plot_path, extend_name, metric_name.replace(' ', '_'))

                with open(file_name, 'a+') as f_out:
                    f_out.write('%s\n' % server)
                    for timestamp, value in zip(metric_data[server]['timestamp'], values):
                        f_out.write('%s %s\n' % (timestamp, value))

    @staticmethod
    def create_simple_plot(data, plot_path, plot_config=None, extend_name=None):
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter

        for metric_name, metric_data in data.items():
            t_server = None
            fig, ax = plt.subplots()
            for server in metric_data.keys():
                if not t_server:
                    t_server = server

                x_values = metric_data[t_server]['timestamp']
                y_values = metric_data[server]['values']
                if len(metric_data[t_server]['timestamp']) != len(metric_data[server]['values']):
                    min_len = min(len(metric_data[t_server]['timestamp']), len(metric_data[server]['values']))
                    x_values = metric_data[t_server]['timestamp'][:min_len]
                    y_values = metric_data[server]['values'][:min_len]

                ax.plot(x_values, y_values, label=server)

            plt.title(metric_name)
            plt.legend()
            plt.xlabel('timestamps')
            plt.xticks(rotation='vertical')

            if plot_config and plot_config.get(metric_name):
                if plot_config.get(metric_name).get('ylim'):
                    ax.set_ylim(plot_config.get(metric_name).get('ylim'))
                if plot_config.get(metric_name).get('ylabel'):
                    plt.ylabel(plot_config.get(metric_name).get('ylabel'))
                if plot_config.get(metric_name).get('format'):
                    ax.yaxis.set_major_formatter(FuncFormatter(plot_config.get(metric_name).get('format')))

            fig = plt.gcf()
            fig.set_size_inches(22.5, 10.5)
            plt.tight_layout()

            plot_file_name = '%s/plot-%s.png' % (plot_path, metric_name.replace(' ', '_'))
            if extend_name:
                plot_file_name = '%s/plot-%s_%s.png' % (plot_path, extend_name, metric_name.replace(' ', '_'))

            plt.savefig(plot_file_name, dpi=600, orientation='landscape')
