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

from threading import Thread
# from random import choices

from ...util import log_print, util_sleep
from .zookeeper import Zookeeper


class ZkNodesRestart(Thread):
    def __init__(self, zk, nodes_amount):
        super().__init__()
        self.setDaemon(True)
        # self.zk: Zookeeper = zk
        self.zk = zk
        self.nodes_amount = nodes_amount
        self.running = True
        self.order = 'seq'
        self.restart_timeout = 5

    def stop(self):
        log_print('Interrupting ZK nodes restarting thread', color='red')
        self.running = False

    def run(self):
        log_print('Starting ZK nodes restarts', color='green')
        while self.running:
            for node_id in self.__get_nodes_to_restart():
                log_print('Killing ZK node {}'.format(node_id), color='debug')
                self.zk.kill_node(node_id)
                util_sleep(self.restart_timeout)
                log_print('Starting ZK node {}'.format(node_id), color='debug')
                self.zk.start_node(node_id)

    def set_params(self, **kwargs):
        self.order = kwargs.get('order', self.order)
        self.restart_timeout = kwargs.get('restart_timeout', self.restart_timeout)
        self.nodes_amount = kwargs.get('nodes_amount', self.nodes_amount)
        log_print('Params set to:\norder={}\nrestart_timeout={}\nnodes_amount={}'
                  .format(self.order, self.restart_timeout, self.nodes_amount))

    def __get_nodes_to_restart(self):
        zk_nodes = list(self.zk.nodes.keys())

        zk_nodes = zk_nodes[:self.nodes_amount]
        # uncomment this when Python 3.7 will be used.
        # if self.order == 'rand':
        #     zk_nodes = choices(zk_nodes[:self.nodes_amount])

        return zk_nodes

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        self.join()

        if exc_type and exc_val and exc_tb:
            raise Exception(exc_tb)

