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

from tiden.logger import get_logger
from tiden.tidenexception import TidenException


class BaseUtility:

    def __init__(self, ignite, parent_cls=None):
        self._parent_cls = parent_cls
        self.latest_utility_output = None
        self.latest_command = None
        self.latest_utility_host = None
        self.ignite = ignite

    def check_content_all_required(self, buff, lines_to_search, maintain_order=False, escape=None):
        """
        This method checks the all lines in lines_to_search list could be found in buff. If not then exception
        TidenException will be risen.

        :param buff:
        :param lines_to_search:
        :return:
        """
        import re
        search_in = [line for line in buff.split('\n') if line]
        if escape:
            escape_from_search = []
            for item_to_escape in escape:
                tmp_ = [line for line in search_in if item_to_escape in line]
                escape_from_search += tmp_
            if escape_from_search:
                search_in = [item for item in search_in if item not in escape_from_search]

        search_for = list(lines_to_search)
        found = []
        result = True

        if maintain_order:
            search_left = search_for.copy()
            for line in search_in:
                if len(search_left) <= 0:
                    break
                cur_search_for = search_left[0]
                m = re.search(cur_search_for, line)
                if m:
                    found.append(cur_search_for)
                    search_left = search_left[1:]

        else:
            for line_to_search in search_for:
                for line in search_in:
                    m = re.search(line_to_search, line)
                    if m:
                        found.append(line_to_search)
        if len(search_for) != len(found):
            get_logger('tiden').debug('Searching \n%s \nand found: \n%s \nin buffer \n%s'
                                      % ('\n'.join(search_for), '\n'.join(found), '\n'.join(search_in)))
            if len(search_for) > len(found):
                raise TidenException('Searching \n%s \nand found: \n%s \nin buffer \n%s.\nCan\'t find:\n%s'
                                 % ('\n'.join(search_for),
                                    '\n'.join(found),
                                    '\n'.join(search_in),
                                    set(search_for).difference(set(found))))
            else:
                raise TidenException('Searching \n%s \nand found: \n%s \nin buffer \n%s.\nFound additional items:\n%s'
                                     % ('\n'.join(search_for),
                                        '\n'.join(found),
                                        '\n'.join(search_in),
                                        set(found).difference(set(search_for))))
        return result