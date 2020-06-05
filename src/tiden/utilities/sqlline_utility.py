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

from ..util import print_green


class Sqlline:
    def __init__(self, ignite, **kwargs):
        self.ignite = ignite
        self.conn_params = ''

        if kwargs.get('ssl_connection'):
            ssl_conn_tuple = kwargs.get('ssl_connection')

            self.conn_params = 'sslMode=require' \
                               '&sslClientCertificateKeyStoreUrl={}' \
                               '&sslClientCertificateKeyStorePassword={}' \
                               '&sslTrustCertificateKeyStoreUrl={}' \
                               '&sslTrustCertificateKeyStorePassword={}'.format(
                ssl_conn_tuple.keystore_path,
                ssl_conn_tuple.keystore_pass,
                ssl_conn_tuple.truststore_path,
                ssl_conn_tuple.truststore_pass)

        if kwargs.get('auth'):
            auth_info = kwargs.get('auth')
            self.conn_params += '&user={}&password={}'.format(auth_info.user, auth_info.password)

    def run_sqlline(self, sql_commands, driver_flags=None, log=True):
        set_java_home = ''
        node_id = self.ignite.get_alive_default_nodes()[0]
        host = self.ignite.nodes[node_id]['host']
        port = self.ignite.nodes[node_id]['client_connector_port']
        sql_cmd_file = self.util_prepare_sql_file(host, sql_commands)

        if self.ignite.config['environment'].get('env_vars') \
                and self.ignite.config['environment']['env_vars'].get('JAVA_HOME'):
            set_java_home = 'export JAVA_HOME="%s";export PATH=$JAVA_HOME/bin:$PATH;' \
                            % self.ignite.config['environment']['env_vars'].get('JAVA_HOME')

        run_sqlline = 'cd {}/bin;{}./sqlline.sh ' \
                      '--color=true ' \
                      '--verbose=true ' \
                      '--showWarnings=true ' \
                      '--force=true ' \
                      '--showNestedErrs=true ' \
                      '--outputFormat=csv ' \
                      '-u '.format(self.ignite.nodes[node_id]['ignite_home'], set_java_home)

        default_conn_str = 'jdbc:ignite:thin://{}:{}'.format(host, port)

        if self.conn_params:
            driver_flags = [self.conn_params] if not driver_flags else driver_flags.insert(0, self.conn_params)

        if driver_flags:
            run_sqlline += '\"{}?{}\"'.format(default_conn_str, '?'.join(driver_flags))
        else:
            run_sqlline += '\"{}\"'.format(default_conn_str)

        run_sqlline += ' -f %s' % sql_cmd_file

        if log:
            print_green(run_sqlline)
        results = self.ignite.ssh.exec_on_host(host, [run_sqlline])
        response = results[host][0]
        if log:
            print_green(response)
            self.util_print_beautiful(response)

        return response

    def util_prepare_sql_file(self, host, sql_commands):
        sql_cmd_file = '%s/sql_commands.sql' % self.ignite.config['rt']['remote']['test_dir']

        # delete sql commands file if exists
        commands = []
        results = self.ignite.ssh.exec_on_host(host, ['rm %s' % sql_cmd_file])
        print_green(results)

        # create sql commands file
        for sql_cmd in sql_commands:
            commands.append('echo %s >> %s' % (sql_cmd, sql_cmd_file))
        print_green(commands)
        results = self.ignite.ssh.exec_on_host(host, commands)
        print_green(results)

        return sql_cmd_file

    @staticmethod
    def util_print_beautiful(buffer):
        for line in buffer.split('\n'):
            print_green(line)

