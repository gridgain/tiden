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

from .util import util_sleep_for_a_while


class StressT:
    fio_path = ''
    default_timeout = 100000

    def __init__(self, ssh):
        self.ssh = ssh

    def get_node_cpu_count(self, host):
        """
        Func return cpu count on host
        :param host: host for run command
        :return: cpu count
        """
        cpu_count = 'cat /proc/cpuinfo | grep processor | wc -l'
        return ''.join(self.ssh.exec_on_host(host, [cpu_count])[host]).rstrip()

    def get_node_ram_count(self, host):
        """
        Func return 75% of free ram on host
        :param host: host for run command
        :return: 75% of free ram
        """
        ram_count = 'head -1 /proc/meminfo | awk \'{printf "%d", $2*0.75/16}\''
        return ''.join(self.ssh.exec_on_host(host, [ram_count])[host]).rstrip()

    def get_random_server_pid(self, host):
        """
        Func return server pid on host
        :param host: host for run command
        :return: pid of server node
        """
        get_pid = \
            'ps -ef | grep ignite | grep java | grep -v client | grep ignite.server | head -n 1 | awk \'{print $2}\''
        return ''.join(self.ssh.exec_on_host(host, [get_pid])[host]).rstrip()

    def get_random_client_pid(self, host):
        """
        Func return client pid on host
        :param host: host for run command
        :return: pid of client node
        """
        get_pid = 'ps -ef | grep ignite | grep java | grep client | head -n 1 | awk \'{print $2}\''
        return ''.join(self.ssh.exec_on_host(host, [get_pid])[host]).rstrip()

    def sigstop(self, host, pid):
        """
        Func run sigstop on pid on host
        :param host: host for run command
        :param pid: pid for run command
        :return: result of sigstop
        """
        sigstop = 'kill -STOP %s' % pid
        return self.ssh.exec_on_host(host, [sigstop])

    def sigstart(self, host, pid):
        """
        Func run sigcont on pid on host
        :param host: host for run command
        :param pid: pid for run command
        :return: result of sigcont
        """
        sigcont = 'kill -CONT %s' % pid
        return self.ssh.exec_on_host(host, [sigcont])

    def fio_start(self, timeout, path, host):
        """
        Func run fio on host during time define by timeout
        :param timeout: timeout - duration of operation
        :param path: path to io file
        :param host: host for io load
        :return: result of fio run command
        """
        fio_command = 'fio --name=test --rw=randrw --rwmixread=20 --size=20g --direct=1 ' \
                      '--runtime=%s --ioengine=libaio --iodepth=4 --numjobs=32 ' \
                      '--directory="%s" --filename=io.test.file >%s/fio_log.log 2>&1 &' % (timeout, path, path)
        return self.ssh.exec_on_host(host, [fio_command])

    def fio_stop(self, timeout, path, host):
        """
        Func run fio on host during time define by timeout
        :param timeout: timeout - duration of operation
        :param path: path to io file
        :param host: host for io load
        :return: result of fio run command
        """
        fio_command = 'fio --name=test --rw=randwrite --rwmixread=0 --size=20g --direct=1 ' \
                      '--runtime=%s --ioengine=libaio --iodepth=4 --numjobs=32 ' \
                      '--directory="%s" --filename=io.test.file >%s/fio_log.log 2>&1 &' % (timeout, path, path)
        return self.ssh.exec_on_host(host, [fio_command])

    def fio_rm_file(self, path, host):
        """
        Func delete fio file
        :param path: path to io file
        :param host: host for delete file after io
        :return: result of delete fio file
        """
        fio_delete = 'rm %s/io.test.file' % path
        return self.ssh.exec_on_host(host, [fio_delete])

    def load_disk(self, path, host, **kwargs):
        """
        Func load disk by call io to rw 20g file
        :param path: path to io file
        :param host: host for io load
        :param kwargs: timeout - duration of operation
        """
        timeout = kwargs.get('timeout', self.default_timeout)

        self.fio_start(timeout, path, host)
        self.fio_rm_file(path, host)

    def load_network(self, server, host, **kwargs):
        """
        Func load network by call iperf from host to server
        :param server: iperf server host
        :param host: host from network load come to server
        :param kwargs: timeout - duration of operation
        """
        timeout = kwargs.get('timeout', self.default_timeout)

        self.iperf_start_server(timeout, server)
        self.iperf_start_load(timeout, server, host)
        self.iperf_kill_process(server)
        self.iperf_kill_process(host)

    def load_cpu(self, host, **kwargs):
        """
        Func load cpu by call stress use max count of cpu
        :param host: host for cpu load
        :param kwargs: timeout - duration of operation
        """
        timeout = kwargs.get('timeout', self.default_timeout)

        cpu_count = self.get_node_cpu_count(host)
        self.stress_load_cpu(timeout, host, cpu_count)

    def load_ram(self, host, **kwargs):
        """
        Func load ram by call stress use 75 % of free ram
        :param host: host for ram load
        :param kwargs: timeout - duration of operation
        """
        timeout = kwargs.get('timeout', self.default_timeout)

        ram_count = self.get_node_ram_count(host)
        self.stress_load_ram(timeout, host, ram_count)

    def sigstop_process(self, host, pid, **kwargs):
        """
        Func run sigstop on pid on host on sigcont on it after timeout
        :param host: host for pid stop/cont
        :param kwargs: timeout - duration of operation, node_type - server or client type of node
        :return: -
        """
        timeout = kwargs.get('timeout', self.default_timeout)

        self.sigstop(host, pid)
        util_sleep_for_a_while(timeout, msg='Sigstop for')
        self.sigstart(host, pid)

    def network_emulate_packet(self, host, dest_host, **kwargs):
        """
        Func run tc for lost/dublicate/corrupt
        :param host: host for tc run to lost/dublicate/corrupt network packet from dest_host
        :param dest_host: dest host from traffic come to host
        :param kwargs: timeout - duration of operation, lost_rate - rate of packet lost/dublicate/corrupt
        :return: -
        """

        timeout = kwargs.get('timeout', self.default_timeout)
        lost_rate = kwargs.get('lost_rate', '5.0%')

        tc_root = 'sudo tc qdisc add dev p2p1 root handle 1: prio'
        tc_parent = 'sudo tc qdisc add dev p2p1 parent 1:3 handle 30: netem %s %s' % (kwargs['type'], lost_rate)
        tc_filter = 'sudo tc filter add dev p2p1 protocol ip parent 1:0 prio 3 u32 match ip dst %s/32 flowid 1:3' \
                    % dest_host
        self.ssh.exec_on_host(host, [tc_root])
        self.ssh.exec_on_host(host, [tc_parent])
        self.ssh.exec_on_host(host, [tc_filter])
        util_sleep_for_a_while(timeout, msg='Emulate network troubles for')
        tc_stop = 'sudo tc qdisc delete dev p2p1 root'
        self.ssh.exec_on_host(host, [tc_stop])

    def network_emulate_packet_loss(self, host, dest_host, **kwargs):
        lost_rate = kwargs.get('lost_rate', '100.0%')
        trouble_type = kwargs.get('type', 'loss')
        tc_root = 'sudo tc qdisc add dev p2p1 root handle 1: prio'
        tc_parent = 'sudo tc qdisc add dev p2p1 parent 1:3 handle 30: netem %s %s' % (trouble_type, lost_rate)
        tc_filter = 'sudo tc filter add dev p2p1 protocol ip parent 1:0 prio 3 u32 match ip dst %s/32 flowid 1:3' \
                    % dest_host
        self.ssh.exec_on_host(host, [tc_root])
        self.ssh.exec_on_host(host, [tc_parent])
        self.ssh.exec_on_host(host, [tc_filter])

    def network_emulate_packet_loss_rollback(self, host):
        tc_stop = 'sudo tc qdisc delete dev p2p1 root'
        self.ssh.exec_on_host(host, [tc_stop])

    def iperf_start_server(self, timeout, host):
        """
        Func start iperf server
        :param host: host from network load come to server
        :param timeout: timeout - duration of operation
        :return: result of start command
        """
        iperf_server = 'iperf -s -D -t %s' % timeout
        return self.ssh.exec_on_host(host, [iperf_server])

    def iperf_start_load(self, timeout, server, host):
        """
        Func start iperf client and run load
        :param server: iperf server host
        :param host: iperf client host
        :param timeout: timeout - duration of operation
        :return: result of command
        """
        iperf_start = 'iperf -c %s --dualtest -P 10 -t %s' % (server, timeout)
        return self.ssh.exec_on_host(host, [iperf_start])

    def iperf_kill_process(self, host):
        """
        Func kill iperf process
        :param host: host for operation
        :return: result of command
        """
        iperf_stop = 'pkill -f -9 iperf'
        return self.ssh.exec_on_host(host, [iperf_stop])

    def stress_load_cpu(self, timeout, host, cpu):
        """
        Func run cpu load ssh command (stress)
        :param timeout: timeout - duration of operation
        :param host: host for operation
        :param cpu: count of cpu used
        :return: result of ssh call stress
        """
        stress_cpu = 'stress --cpu %s -t %s' % (cpu, timeout)
        return self.ssh.exec_on_host(host, [stress_cpu])

    def stress_load_ram(self, timeout, host, ram):
        """
        Func run ram load ssh command (stress)
        :param timeout: timeout - duration of operation
        :param host: host for operation
        :param ram: count of ram used (in bytes)
        :return: result of ssh call stress
        """
        stress_ram = 'stress --vm-bytes %sk --vm-keep -m 16 -t %s' % (ram, timeout)
        return self.ssh.exec_on_host(host, [stress_ram])

