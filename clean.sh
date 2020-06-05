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


SCRIPT_PATH="$(cd "$(dirname $0)"; pwd)" # "

pushd $SCRIPT_PATH >/dev/null

find . -name __pycache__ -type d | xargs -I {} rm -rf {}
find . -name .pytest_cache -type d | xargs -I {} rm -rf {}
find . -name "*.egg-info" -type d | xargs -I {} rm -rf {}

rm -rf .eggs
rm -rf .tox
rm -rf build
rm -rf dist

# remove remnants of previous `setup.py develop`
for script_name in `ls -1 $SCRIPT_PATH/bin/*.py`; do
  for bin_path in /usr/local/bin /usr/bin ~/.local/bin; do
    if [ -f $bin_path/$script_name ]; then
      sudo rm -f $bin_path/$script_name
    fi
  done
done

if python3.7 -m site | grep tiden 2>/dev/null 1>&2; then
  echo "Please, clean following from sys.path manually"
  python3.7 -m site | grep tiden 2>/dev/null
fi

popd >/dev/null
