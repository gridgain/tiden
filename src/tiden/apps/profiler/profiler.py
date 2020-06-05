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

import os

from ..app import App
from ..appexception import AppException, MissedRequirementException
from ...util import log_print


class Profiler(App):
    jfr_jvm_opts = "-XX:+UnlockCommercialFeatures" \
                   " -XX:+FlightRecorder" \
                   " -XX:StartFlightRecording=delay={WARMUP}s," \
                   "duration={DURATION}s," \
                   "filename={JFR_PATH}," \
                   "settings={JFC_PATH}"
    available_profilers = ('jfr', 'async_flamegraph')

    def __init__(self, name, config, ssh, profiler=''):
        super().__init__(name, config, ssh, app_type='profiler')
        self.type = self.config['environment'].get('yardstick', {}).get('profiler')
        if not self.type:
            self.type = profiler
        if self.type not in self.available_profilers:
            raise AppException(f"Unknown profiler type {self.type}. Available types: {self.available_profilers}")
        self.async_profiler_home = os.path.join(self.config['remote']['suite_var_dir'], 'flamegraph', 'async_fmg')
        self.options = {
            'warmup': 60,
            'duration': 60,
            'bench_name': ''
        }

    def check_requirements(self):
        if self.type == 'jfr':
            self.require_artifact('jfr_cfg')
        else:
            self.require_artifact(self.type)

    def update_options(self, **kwargs):
        if kwargs:
            self.options.update(kwargs)

    def check_hosts_for_async_profiler(self, hosts):
        # async_profiler requires 'perf_event_paranoid' and 'kptr_restrict' to be set to '1' and '0' respectively
        # https://github.com/jvm-profiling-tools/async-profiler#basic-usage
        check_cmd = ['cat /proc/sys/kernel/perf_event_paranoid',
                     'cat /proc/sys/kernel/kptr_restrict']
        check_cmds = {}
        for h in hosts:
            check_cmds[hosts[h]['host']] = check_cmd

        out = self.ssh.exec(check_cmds)

        err_msg = ""
        for host in out.keys():
            res_str = ''.join(out[host])
            res_str_exp = "1\n0\n"
            if res_str != res_str_exp:
                if len(err_msg) == 0:
                    err_msg += "Unsatisfied requirement for async_profiler found\n"
                    err_msg += f"Command: {'; '.join(check_cmd)} on host {host}:\n"
                err_msg += f"Expected:\n{res_str_exp}\n" + \
                    f"Actual:\n{res_str}\n"
        if len(err_msg) > 0:
            raise MissedRequirementException(err_msg)

    def get_jvm_options(self):
        if self.type == 'jfr':
            jfr_str = self.jfr_jvm_opts.format(
                WARMUP=self.options['warmup'],
                DURATION=self.options['duration'],
                JFR_PATH=os.path.join(
                    self.config['rt']['remote']['test_dir'],
                    'jfr-{b}-d{d}.jfr'.format(b=self.options['bench_name'], d=self.options['duration'])),
                JFC_PATH=self.config['artifacts']['jfr_cfg']['remote_path'])
            return jfr_str.split(' ')
        else:
            return []

    def start(self):
        warmup = self.options['warmup']
        duration = self.options['duration']
        nodes = self.options.get('nodes')

        if self.type == "jfr":
            log_print("Will be used profiler: {profiler}\nYou no need to call start method.".format(
                profiler=self.type))
        elif self.type == "async_flamegraph":
            # Checks
            if nodes is None:
                log_print(f"No Ignite nodes info available. Will not start profiler of type {self.type}", color='red')
                return
            self.check_hosts_for_async_profiler(nodes)

            output_dir = self.config['rt']['remote']['test_dir']
            for node_id in nodes.keys():
                pid = nodes[node_id]['PID']
                host = nodes[node_id]['host']

                out_file_basename = os.path.join(output_dir, f"fmgrh-pid-{pid}")
                out_file_fmg = out_file_basename + '.svg'
                out_file_log = out_file_basename + '.log'

                self.ssh.exec_on_host(host, [
                    f"chmod +x {self.async_profiler_home}/*.sh",
                    f"chmod +x {self.async_profiler_home}/build/*"
                ])

                cmd = f"sleep {warmup}; " + \
                      f"{self.async_profiler_home}/profiler.sh " + \
                      f"-d {duration} -i 999000 -b 5000000 -o svg -f {out_file_fmg} {pid}"
                cmds = [f"nohup bash -c '{cmd}' >{out_file_log} 2>&1 &"]

                log_print(f"Starting profiler on host {host}")
                log_print('; '.join(cmds), color='debug')

                self.ssh.exec_on_host(host, cmds)

    def stop(self):
        if self.type == 'jfr':
            return

        # Since async profiler is started with 'duration' option,
        #  there is no need to stop it explicitly
        if self.type == "async_flamegraph":
            return

