#/bin/bash
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


sudo pip3.7 uninstall -y tiden tiden_gridgain twine keyring keyrings.alt

# remove remnants of previous `setup.py develop`
for script_name in run_tests merge_yaml_reports patch_artifacts_config prepare_apache_ignite_builds; do
  for bin_path in /usr/local/bin /usr/bin ~/.local/bin; do
    if [ -f $bin_path/$script_name.py ]; then
      sudo rm -f $bin_path/$script_name.py
    fi
  done
done
