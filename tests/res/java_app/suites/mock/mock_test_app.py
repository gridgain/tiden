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

from tiden.case import AppTestCase
from tiden.apps import JavaApp
from time import sleep


class MockTestApp(AppTestCase):
    def __init__(self, *args):
        super().__init__(*args)
        self.add_app('mockapp')

    def test_wait_message(self):
        app: JavaApp = self.get_app('mockapp')
        for node_idx in app.nodes.keys():
            app.rotate_node_log(node_idx)
        self.tiden.ssh.exec_at_nodes(app.nodes, lambda node_idx, node: f"echo 'Message' > {node['log']}")
        sleep(1)
        assert app.wait_message("Message")
        assert not app.wait_message('Absent', timeout=3)
