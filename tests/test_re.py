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

import unittest
import re

RE_LINK = re.compile(r'((http|ftp)s?://[^ ]+)')
RE_LINK_WITH_NAME = re.compile(r'(?:((?:http|ftp)s?://[^\[ ]*)\[([^\]]*)\])')


def process_links(r):
    # convert  'http:/blah.com' to '[http://blah.com]' and
    # 'http://blah.com[blah]' to '[blah|http://blah.com]'

    start = 0
    res = RE_LINK.search(r, start)
    while res is not None:
        res0 = RE_LINK_WITH_NAME.search(r, start)
        if res0 is not None:
            res = res0
            link = res.group(1)
            name = res.group(2)
            r0 = r[:res.start(1)] + '[' + name + '|' + link + ']'
            r = r0 + r[res.end(2) + 1:]
            start = len(r0) + 1
        else:
            link = res.group(1)
            r0 = r[:res.start(1)] + '[' + link + ']'
            r = r0 + r[res.end(1) + 1:]
            start = len(r0) + 1
        res = RE_LINK.search(r, start)
    return r


class MyTestCase(unittest.TestCase):
    def test_something(self):
        self.assertTrue(re.search(RE_LINK, "") is None)
        self.assertTrue(re.search(RE_LINK, "http://blah.com") is not None)
        self.assertTrue(re.search(RE_LINK, "https://blah.com") is not None)
        self.assertTrue(re.search(RE_LINK, "blah.com") is None)

    def test_someg(self):
        self.assertTrue(re.search(RE_LINK_WITH_NAME, "") is None)
        self.assertTrue(re.search(RE_LINK_WITH_NAME, "http://blah.com[blah]") is not None)
        self.assertTrue(re.search(RE_LINK_WITH_NAME, "https://blah.com[ds dw.sds]") is not None)
        self.assertTrue(re.search(RE_LINK_WITH_NAME, "blah.com") is None)
        self.assertTrue(re.search(RE_LINK_WITH_NAME, "http://blah.com") is None)
        self.assertTrue(re.search(RE_LINK_WITH_NAME, "http://blah.com[e ") is None)
        self.assertTrue(re.search(RE_LINK_WITH_NAME, "http://blah.com [e dwe]") is None)

    def test_m(self):
        res = re.match(RE_LINK, "http://blah.com [e dwe]")
        self.assertTrue(res is not None)
        self.assertEqual("http://blah.com", res.group(1))

    def test_m1(self):
        res = re.match(RE_LINK_WITH_NAME, "http://blah.com [e dwe]")
        self.assertTrue(res is None)

    def test_m2(self):
        res = re.match(RE_LINK_WITH_NAME, "http://blah.com[e dwe]")
        self.assertTrue(res is not None)
        self.assertEqual(res.group(1), "http://blah.com")
        self.assertEqual(res.group(2), "e dwe")

    def test_m3(self):
        s = "holy http://blah.com[e dwe] shmoly"
        res = re.search(RE_LINK_WITH_NAME, s)
        self.assertTrue(res is not None)
        self.assertEqual(res.group(1), "http://blah.com")
        self.assertEqual(res.group(2), "e dwe")

        o = s[:res.start(1)] + "Q" + s[res.end(2) + 1:]
        self.assertEqual("holy Q shmoly", o)

    def test_pr(self):
        s = process_links('blah http://bbbb.com[GG-dd] woo')
        self.assertEqual('blah [GG-dd|http://bbbb.com] woo', s)

    def test_pr1(self):
        s = process_links('blah http://bbbb.com[GG-dd] woo and http://www.com')
        self.assertEqual('blah [GG-dd|http://bbbb.com] woo and [http://www.com]', s)

if __name__ == '__main__':
    unittest.main()

