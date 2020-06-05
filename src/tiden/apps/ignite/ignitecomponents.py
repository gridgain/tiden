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

from .components import *


class IgniteComponents(
    IgniteControlThreadMixin,
    IgniteBinRestMixin,
    IgniteJmxMixin,
    IgniteRESTMixin,
    IgniteCommunicationMixin,
    IgniteIDMixin,
    IgniteLibsMixin,
    IgniteStaticInitMixin,
    IgniteTopologyMixin,
    IgniteLogDataMixin,
    IgniteNodesMixin,
):
    def __init__(self, *args, **kwargs):
        # print('IgniteComponents.__init__')
        super(IgniteComponents, self).__init__(*args, **kwargs)

    def do_callback(self, callback_name, *args, **kwargs):
        """
        Invoke callback from all mixins that have it.
        :param callback_name:
        :param args:
        :param kwargs:
        :return:
        """
        cc = []
        cl = self.__class__.__mro__ if kwargs.get('reversed', False) else reversed(self.__class__.__mro__)
        for c in cl:
            if hasattr(c, callback_name):
                m = getattr(c, callback_name)
                if m not in cc:
                    m(self, *args, **kwargs)
                    cc.append(m)

