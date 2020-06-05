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

from pprint import PrettyPrinter

from tiden.tidenplugin import TidenPlugin
from tiden.dockermanager import DockerManager

TIDEN_PLUGIN_VERSION = '1.0.0'


class DockerCleaner(TidenPlugin):
    pp = PrettyPrinter()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def before_hosts_setup(self, *args, **kwargs):
        self.dockermanager = DockerManager(self.config, self.ssh)
        force_setup = self.config.get('force_setup', False) or self.options.get('force_setup', False)
        containers_count = self.dockermanager.print_and_terminate_containers(force_setup)
        if containers_count == 0:
            self.log_print('all containers removed successfully', color='green')
        elif containers_count > 0:
            if self.options.get('force_setup', False):
                exit('some containers don\'t deleted.  The runner will be stopped')
            else:
                exit('WARNING: Found docker containers and flag force_setup for DockerCleaner isn\'t set. '
                     'The runner will be stopped')
        else:
            self.log_print('No running docker containers found on hosts', color='green')