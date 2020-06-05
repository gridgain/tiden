#!/bin/bash
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


SCRIPT_PATH="$(cd "$(dirname "$0")"; "pwd")"; # "
pushd $SCRIPT_PATH >/dev/null

sudo -H pip3.7 install dist/tiden-*-py3-none-any.whl

popd >/dev/null
