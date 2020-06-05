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

from .util import version_num
import re


class AttrObj:
    def __init__(self, value, attrname, parent=None, negated=False):
        self.value = value
        self.__doc__ = attrname
        self.__parent__ = parent
        self.__negated__ = negated

    def __str__(self):
        result = str(self.value)
        if '$' in result and self.__parent__ is not None:
            result = self.__parent__._get_top_level_parent()._patch_attribute(self.__doc__, result)
        return result

    def __int__(self):
        return int(self.value)

    def __bool__(self):
        return bool(self.value)

    def __eq__(self, other):
        return self.value == other

    def __getitem__(self, item):
        return self.value[item]

    def __mul__(self, other):
        return self.value * other

    def __rmul__(self, other):
        return other * self.value

    def __add__(self, other):
        return self.value + other

    def __radd__(self, other):
        return other + self.value

    def __invert__(self):
        return AttrObj(not self.value, self.__doc__, self.__parent__, not self.__negated__)

    def __name__(self):
        name = [self.__doc__]
        parent = self.__parent__
        while parent is not None:
            name.append(parent.__doc__)
            parent = parent.__parent__
        name.reverse()
        if self.__negated__:
            return 'not ' + '.'.join(name)
        return '.'.join(name)


class Dict2Obj:
    re_patch = re.compile(r'\$\{([^}]+)\}')

    def __init__(self, obj, dictname='?', parent=None):
        self.obj = obj
        self.__doc__ = dictname
        self.__parent__ = parent

    def _get_top_level_parent(self):
        if self.__parent__ is not None:
            return self.__parent__._get_top_level_parent()
        return self

    def _patch_attribute(self, attribute_name, attribute_value):
        pos = 0
        value = attribute_value
        while pos < len(value):
            m = Dict2Obj.re_patch.search(value, pos)
            if m is not None:
                pos = m.start(0) + len(m.group(0))
                if m.group(1) != attribute_name:
                    value = \
                        value[0:m.start(0)] + \
                        str(getattr(self, m.group(1))) + \
                        value[pos:]
            else:
                pos = len(value)
        return value

    def update(self, obj):
        self.obj.update(obj)

    def __getattr__(self, item):
        """
        attribute resolution:
        1. getter, if exists
        2. magic method 'num_XXX' returns len(XXX)
        3. recursive resolution
        :param item:
        :return:
        """
        if 'get_' + item in self.__class__.__dict__:
            return getattr(self, 'get_' + item)()
        elif item.startswith('num_'):
            _item = item[4:]
            if _item in self.obj:
                return len(self.obj.get(_item))
            else:
                return 0
        else:
            if item in self.obj:
                if isinstance(self.obj.get(item), dict):
                    return Dict2Obj(self.obj.get(item), item)
                return AttrObj(self.obj.get(item), item, self)
            if 'enabled' in item:
                return AttrObj(None, item, self)
            else:
                return None

    def __len__(self):
        return len(self.obj)


class TidenEnvironmentConfig(Dict2Obj):
    def __init__(self, obj, dictname='environment', parent=None):
        super(TidenEnvironmentConfig, self).__init__(obj, dictname, parent)

    def get_num_server_nodes(self):
        return self.num_server_hosts * self.servers_per_host

    def get_num_client_nodes(self):
        return self.clients_per_host * self.num_client_hosts

    def __getitem__(self, item):
        if item in self.obj:
            if isinstance(self.obj.get(item), dict):
                return Dict2Obj(self.obj.get(item), item)
            return AttrObj(self.obj.get(item), item, self)
        if 'enabled' in item:
            return AttrObj(None, item, self)
        if 'hosts' in item:
            self.obj[item] = []
            return self.obj[item]
        return None


class TidenRemoteConfig(Dict2Obj):
    def __init__(self, obj, dictname='remote', parent=None):
        super(TidenRemoteConfig, self).__init__(obj, dictname, parent)


class TidenSshConfig(Dict2Obj):
    def __init__(self, obj, dictname='ssh', parent=None):
        super(TidenSshConfig, self).__init__(obj, dictname, parent)

    def __getitem__(self, item):
        if item in self.obj:
            if isinstance(self.obj.get(item), dict):
                return Dict2Obj(self.obj.get(item), item)
            return AttrObj(self.obj.get(item), item, self)
        if 'hosts' in item:
            self.obj[item] = []
            return self.obj[item]
        return None


class TidenIgniteConfig(Dict2Obj):
    def __init__(self, obj, dictname='ignite', parent=None):
        super(TidenIgniteConfig, self).__init__(obj, dictname, parent)


class TidenArtifactsConfig(Dict2Obj):
    def __init__(self, obj, dictname='artifacts', parent=None):
        super(TidenArtifactsConfig, self).__init__(obj, dictname, parent)

    def __getitem__(self, item):
        if item not in self.obj.keys():
            self.obj[item] = {}
        else:
            assert isinstance(self.obj.get(item), dict)
        return Dict2Obj(self.obj.get(item), item)
        # return AttrObj(self.obj.get(item), item, self)
        # return Dict2Obj(self.obj.get(item), item)

    def get_ignite(self, ignite_name=None):
        if ignite_name is None:
            ignite_name = 'ignite'
        if ignite_name in self.obj.keys():
            return Dict2Obj(self.obj[ignite_name], ignite_name)
        for artifact_name, artifact_data in self.obj.items():
            if 'type' in artifact_data and artifact_data['type'] == 'ignite':
                return Dict2Obj(artifact_data, artifact_name)
        return Dict2Obj({})


class TidenConfig(Dict2Obj):
    def __init__(self, obj, dictname='config'):
        super(TidenConfig, self).__init__(obj, dictname)

    def __getattr__(self, item):
        if item == 'environment':
            if 'environment' not in self.obj:
                self.obj['environment'] = {}
            return TidenEnvironmentConfig(self.obj['environment'], 'environment', self)
        elif item == 'artifacts':
            if 'artifacts' not in self.obj:
                self.obj['artifacts'] = {}
            return TidenArtifactsConfig(self.obj['artifacts'], 'artifacts', self)
        elif item == 'remote':
            if 'remote' not in self.obj:
                self.obj['remote'] = {}
            return TidenRemoteConfig(self.obj['remote'], 'remote', self)
        elif item == 'ssh':
            if 'ssh' not in self.obj:
                self.obj['ssh'] = {}
            return TidenSshConfig(self.obj['ssh'], 'ssh', self)
        elif item == 'ignite':
            if 'ignite' not in self.obj:
                self.obj['ignite'] = {}
            return TidenIgniteConfig(self.obj['ignite'], 'ignite', self)
        return super(TidenConfig, self).__getattr__(item)

    def get_ignite_version(self, artifact_name=None):
        return self.artifacts.get_ignite(artifact_name).ignite_version

    def get_ignite_version_num(self, artifact_name=None):
        ig_version = self.get_ignite_version(artifact_name)
        assert ig_version is not None
        return version_num(str(ig_version))

    def get_gridgain_version(self, artifact_name=None):
        return self.artifacts.get_ignite(artifact_name).gridgain_version

    def get_gridgain_version_num(self, artifact_name=None):
        gg_version = self.get_gridgain_version(artifact_name)
        assert gg_version is not None
        return version_num(str(gg_version))

