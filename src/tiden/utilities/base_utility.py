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

    def check_content_all_required(self, buff, lines_to_search, maintain_order=False, escape=None,
                                   match_once_or_more=False):
        """
        This method checks the all lines in lines_to_search list could be found in buff. If not then exception
        TidenException will be risen.

        :param buff: text buffer to search in as a single string
        :param lines_to_search: a string or a list of strings to search for (regex is allowed)
        :param maintain_order: every string from lines_line_to_search must match in exactly the same order
        :param escape: a list of strings to exclude from the text buffer
        :param match_once_or_more: allow to match the same search string more than once
        :return: True
        """
        import re

        search_in = [line for line in buff.split('\n') if line]
        if isinstance(lines_to_search, list):
            lines_to_search_0 = lines_to_search
        else:
            lines_to_search_0 = [lines_to_search]

        search_for_iter = iter(lines_to_search_0)
        if maintain_order:
            search_for = [next(search_for_iter)]
        else:
            search_for = lines_to_search_0

        found = []
        match_found = False

        # Iterate through all input lines
        for line_in in search_in:
            # Skip current line if it matches any line from the "escape" list
            if escape and any(map(lambda esc_line: esc_line in line_in, escape)):
                continue

            # Pick a next search string from "lines_to_search"
            if maintain_order and match_found:
                next_search_str = next(search_for_iter, None)
                search_for = [next_search_str] if next_search_str else []

            match_found = False

            # Find if current input line matches any line from "lines_to_search"
            for line_to_search in search_for:
                m = re.search(line_to_search, line_in)
                if m:
                    match_found = True
                    if not match_once_or_more or line_to_search not in found:
                        found.append(line_to_search)
                    break

        # Check results
        if len(lines_to_search_0) != len(found):
            search_for_str = '\n'.join(lines_to_search_0)
            found_str = '\n'.join(found)
            search_in_str = '\n'.join(search_in)
            debug_str = '\n'.join([
                    f"> Searching for:",
                    f"{search_for_str}",
                    f"> Found:",
                    f"{found_str}",
                    f"> In buffer:",
                    f"{search_in_str}",
                ]
            )

            get_logger('tiden').debug(debug_str)

            search_for_uniq = set(lines_to_search_0)
            found_uniq = set(found)

            if len(lines_to_search_0) > len(found):
                raise TidenException(
                    '\n'.join([
                        f"{debug_str}",
                        f"> Can't find:",
                        f"{search_for_uniq - found_uniq}"
                    ])
                )
            else:
                # len(search_for) < len(found)
                raise TidenException(
                    '\n'.join([
                        f"{debug_str}",
                        f"Found additional items:",
                        f"{found_uniq - search_for_uniq}"
                    ])
                )

        return True
