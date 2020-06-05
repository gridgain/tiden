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

from ..singleton import singleton
from ..tidenexception import TidenException
from ..tidenfabric import TidenFabric
from itertools import chain


@singleton
class AppFactory:
    def __init__(self):
        hook_mgr = TidenFabric().get_hook_mgr()
        # [ "tiden.apps.", "tiden_gridgain.apps.", "" ]
        self.applications_paths = list(chain(*hook_mgr.hook.tiden_get_applications_path()))

    def get_app_package(self, app_class_package_name, app_class_name, app_name):
        for applications_path in self.applications_paths:
            try:
                application_package_path = applications_path + app_class_package_name
                app_pkg = __import__(application_package_path, globals(), locals(), [app_class_name], 0)
                return app_pkg
            except ImportError as e:
                pass
        raise TidenException(
            f"Can't import application class '{app_class_name}' for application '{app_name.title()}' "
            f"from package '{app_class_package_name}': package was not found in paths ({self.applications_paths})"
        )

