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

from setuptools import find_packages, setup
import re
import sys
from os.path import join, dirname, isfile, exists
from os import listdir

version = ''
with open(join('src', 'tiden', '__version__.py'), 'r') as fd:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', fd.read(), re.MULTILINE).group(1)

if not version:
    raise RuntimeError('Cannot find version information')

if not exists('requirements.txt'):
    raise RuntimeError('Cannot find requirements information')

with open('requirements.txt', 'r') as fd:
    requirements = [req.strip() for req in fd.readlines() if not req.strip().startswith('#')]

setup(
    version=version,
    platforms=["any"],
    keywords="testing ignite",
    license="apache2.0",
    url="http://github.com/gridgain/tiden",
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    python_requires='>=3.7, <4',
    entry_points={'console_scripts': ['tiden=tiden.console.main:main']},
    install_requires=requirements,
)

