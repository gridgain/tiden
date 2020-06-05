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

from .result import Result, ResultLinesCollector
from .sshpool import SshPool
from .tidenexception import TidenException
from .util import *
from .assertions import *

import pluggy
hookimpl = pluggy.HookimplMarker("tiden")
"""Marker to be imported and used in Tiden hooks implementations"""

