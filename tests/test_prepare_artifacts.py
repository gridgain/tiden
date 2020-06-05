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

import tarfile
from os import mkdir, walk, listdir
from os.path import abspath, join, pardir, exists, basename, dirname, getmtime
from shutil import rmtree
from time import time, sleep
from zipfile import ZipFile

from pytest import fixture

from tiden.artifacts import prepare
from tiden.localpool import LocalPool
from tiden.runner import setup_test_environment, init_remote_hosts, upload_artifacts

config = None
var_dir = None


def get_parent(path):
    return abspath(join(path, pardir))


def ensure_dir(path):
    if not exists(path):
        mkdir(path)


def c_time(path):
    """
    Creation time
    """
    return getmtime(path)

@fixture

def temp_dir(tmpdir_factory):
    fn = tmpdir_factory.mktemp("var")
    global var_dir
    var_dir = fn.strpath
    return fn


def add_from_another_zip(custom_config, artifacts):
    custom_config["artifacts"] = {
        'source_zip': {
            'glob_path': artifacts['source']["arch"]["path"],
            'remote_unzip': True,
            'repack': [
                "copy $additional_tar$/{} self:/".format(artifacts['additional']["file"]["name"])
            ]
        },
        'additional_tar': {
            'glob_path': artifacts['additional']["arch"]["path"],
            'remote_unzip': True
        },
        'additional_file': {
            'glob_path': artifacts['additional']["file"]["path"],
        }
    }
    return custom_config


def make_tar_files(custom_config):
    inner_dir_name = "inner_dir"
    inner_dir_path = join(custom_config["_artifacts_sources"], inner_dir_name)
    mkdir(inner_dir_path)

    # making simple source artifact
    source_artifact_file_name = 'source_artifact.txt'
    source_artifact_file_path = join(inner_dir_path, source_artifact_file_name)
    with open(source_artifact_file_path, 'w') as file:
        file.write("source text")

    tar_gz_name = "tar_gz_artifact.tar.gz"
    tar_gz_path = join(custom_config["_artifacts_sources"], tar_gz_name)

    with tarfile.open(tar_gz_path, "w|gz") as tar:
        tar.add(inner_dir_path, arcname=inner_dir_name)

    tar_name = "tar_artifact.tar"
    tar_path = join(custom_config["_artifacts_sources"], tar_name)

    with tarfile.open(tar_path, "w|") as tar:
        tar.add(inner_dir_path, arcname=inner_dir_name)

    tar_repack_name = "tar_artifact_repack.tar"
    tar_repack_path = join(custom_config["_artifacts_sources"], tar_repack_name)

    with tarfile.open(tar_repack_path, "w|") as tar:
        tar.add(inner_dir_path, arcname=inner_dir_name)

    custom_config["artifacts"] = {
        "tar_artifact": {
            "glob_path": tar_path,
            "remote_unzip": True,
        },
        "tar_artifact_repack": {
            "glob_path": tar_repack_path,
            "remote_unzip": True,
            "repack": [
                "mkdir self:/second_inner_dir"
            ]
        },
        "tar_gz_artifact": {
            "glob_path": tar_gz_path,
            "remote_unzip": True,
        }
    }

    return custom_config


def make_basic_artifacts(custom_config, add_function=None, text="There is gonna be funny"):
    # making simple source artifact
    source_artifact_file_name = 'source_artifact.txt'
    source_artifact_file_path = join(custom_config["_artifacts_sources"], source_artifact_file_name)
    with open(source_artifact_file_path, 'w') as file:
        file.write(text)

    # making simple zip file with single source file
    source_artifact_zip_name = 'source_artifact_arch.zip'
    source_artifact_zip_path = join(custom_config["_artifacts_sources"], source_artifact_zip_name)
    with ZipFile(source_artifact_zip_path, 'w') as arch:
        arch.write(source_artifact_file_path, basename(source_artifact_file_path))

    # making additional file which will be added to source zip file
    additional_artifact_file_name = 'additional_artifact.txt'
    additional_artifact_file_path = join(custom_config["_artifacts_sources"], additional_artifact_file_name)
    with open(additional_artifact_file_path, 'w') as file:
        file.write(text)

    # making additional zip file where we will be taking simple file to source zip
    additional_artifact_tar_name = 'additional_artifact_arch.tar'
    additional_artifact_tar_path = join(custom_config["_artifacts_sources"], additional_artifact_tar_name)
    with tarfile.open(additional_artifact_tar_path, 'w') as arch:
        arch.add(additional_artifact_file_path, arcname=basename(additional_artifact_file_path))

    # collect all information about test artifacts
    test_artifacts = {
        "source": {
            'file': {
                'path': source_artifact_file_path,
                'name': source_artifact_file_name
            },

            'arch': {
                'path': source_artifact_zip_path,
                'name': source_artifact_zip_name,
                'repack_name': source_artifact_zip_name.replace(".zip", ".repack.zip")
            }
        },
        "additional": {
            'file': {
                'path': additional_artifact_file_path,
                'name': additional_artifact_file_name
            },

            'arch': {
                'path': additional_artifact_tar_path,
                'name': additional_artifact_tar_name,
            }
        },
        "sha": {
            "name": "tiden_repack_original.checksum.sha256"
        }
    }

    if add_function:
        custom_config = add_function(custom_config, test_artifacts)
        custom_config["_test_artifacts"] = test_artifacts
        return custom_config
    else:
        return test_artifacts


def make_local_structure(custom_config, exclude_property_dirs=None):
    # make dir for all unit tests
    tests_var_dir = join(var_dir, 'unit_tests')
    ensure_dir(tests_var_dir)

    # make dir for this module
    file_name = basename(__file__)
    test_dir_name = file_name.replace('test_', "").replace('.py', '')
    test_dir_path = join(tests_var_dir, test_dir_name)
    ensure_dir(test_dir_path)

    # make unit test temp dir
    test_temp_dir = join(test_dir_path, "test_temp")
    ensure_dir(test_temp_dir)

    test_var_dir = join(test_dir_path, 'var')
    ensure_dir(test_var_dir)

    # make local tests dir
    local_test_metadata_dir = join(test_var_dir, 'preparation-suite-name-{}'.format(str(time()).replace(".", "-")))
    ensure_dir(local_test_metadata_dir)

    # make temp dir for this module
    local_test_temp_var_dir = join(local_test_metadata_dir, 'tmp')
    ensure_dir(local_test_temp_var_dir)

    # make dir for artifacts
    local_artifacts_dir = join(test_var_dir, 'artifacts')
    ensure_dir(local_artifacts_dir)

    remote_home_dir = join(test_dir_path, 'remote')
    ensure_dir(remote_home_dir)

    # make dir for artifacts source
    local_artifacts_sources_dir = join(test_dir_path, 'artifacts_sources')
    ensure_dir(local_artifacts_sources_dir)

    additional_config = {
        'var_dir': test_var_dir,
        'artifacts_dir': local_artifacts_dir,
        'suite_var_dir': local_test_metadata_dir,
        'tmp_dir': local_test_temp_var_dir,
        "ssh": {
            "home": remote_home_dir
        },
        'environment': {
            'home': remote_home_dir
        },
        "remote": {
            "artifacts_dir": join(remote_home_dir, 'artifacts'),
            "suite_var_dir": join(remote_home_dir, 'test-0')
        },
        "_artifacts_sources": local_artifacts_sources_dir,
        "_test_temp_dir": test_temp_dir
    }

    custom_config.update(additional_config)
    if exclude_property_dirs is not None:
        for exclude_property_dir in exclude_property_dirs:
            if exists(custom_config[exclude_property_dir]):
                rmtree(custom_config[exclude_property_dir])
            del custom_config[exclude_property_dir]
    return custom_config

@fixture

def prepare_test_artifacts():
    global prepare_artifacts_result
    global config

    config = make_local_structure({})
    config = make_basic_artifacts(config, add_function=add_from_another_zip)

    # execute artifacts preparation
    prepare_artifacts_result, config = prepare(config)

@fixture

def prepare_without_local_structure():
    global config
    config = make_local_structure({}, exclude_property_dirs=['artifacts_dir', 'suite_var_dir', 'tmp_dir'])
    config = make_basic_artifacts(config, add_function=add_from_another_zip)
    additional_configs = {
        "dir_prefix": "test-0",
        'environment': {
            "username": "test_user",
            "private_key_path": "/test/path/to/ssh",
            'home': '/test/path/to/home'
        },
        'ssh': {}
    }
    config.update(additional_configs)

@fixture

def prepare_remote_structure():
    global config
    config = {"clean": None}
    config = make_local_structure(config, exclude_property_dirs=['artifacts_dir', 'suite_var_dir', 'tmp_dir'])
    ssh_config = {
        'hosts': ["127.0.0.1"],
        'username': '',
        'private_key_path': '',
        'threads_num': 1
    }
    config["ssh"].update(ssh_config)

@fixture

def prepare_artifacts_with_ssh_structure():
    global config
    global prepare_artifacts_result
    config = {"clean": None}
    config = make_local_structure(config)
    config = make_basic_artifacts(config, add_function=add_from_another_zip)
    prepare_artifacts_result, config = prepare(config)

    ssh_config = {
        'hosts': ["127.0.0.1"],
        'username': '',
        'private_key_path': '',
        'threads_num': 1
    }
    config["ssh"].update(ssh_config)

@fixture

def simple_structure():
    global config
    global prepare_artifacts_result
    config = {"clean": None}
    config = make_local_structure(config)
    config = make_tar_files(config)
    prepare_artifacts_result, config = prepare(config)

    ssh_config = {
        'hosts': ["127.0.0.1"],
        'username': '',
        'private_key_path': '',
        'threads_num': 1
    }
    config["ssh"].update(ssh_config)


def test_prepare_test_artifacts_directory_is_empty(temp_dir, prepare_test_artifacts):
    """
    After preparation temp directory should be cleaned
    """
    found_files = []
    found_dirs = []
    for root, dir, file in walk(config["tmp_dir"]):
        found_files = found_files + file
        found_dirs = found_dirs + dir
    assert found_files == []
    assert found_dirs == []


def test_prepare_test_artifacts_old_artifact_deletion(temp_dir, prepare_test_artifacts):
    """
    Repack should create new file with .repack. addition and remove old archive
    """
    additional_zip_path = join(config["artifacts_dir"], config["_test_artifacts"]['source']["arch"]["name"])
    repack_additional_zip_path = additional_zip_path.replace('.zip', '.repack.zip')
    assert exists(repack_additional_zip_path)
    assert not exists(additional_zip_path)


def test_prepare_test_artifacts_repack_contains(temp_dir, prepare_test_artifacts):
    """
    Repack should add to source file one file from additional artifact
    """
    additional_zip_path = join(config["artifacts_dir"], config["_test_artifacts"]['source']["arch"]["name"])
    repack_additional_zip_path = additional_zip_path.replace('.zip', '.repack.zip')

    with ZipFile(repack_additional_zip_path, 'r') as repack_zip:
        repack_zip.extractall(config["_test_temp_dir"])
    expected_files = [config["_test_artifacts"]['additional']["file"]["name"],
                      config["_test_artifacts"]['source']["file"]["name"],
                      config["_test_artifacts"]["sha"]["name"]]
    found_files = []
    found_dirs = []
    for root, dir, file in walk(config["_test_temp_dir"]):
        found_files = found_files + file
        found_dirs = found_dirs + dir
    assert sorted(found_files) == sorted(expected_files)
    assert found_dirs == []


def test_repeat_prepare_existed_artifacts(temp_dir, prepare_test_artifacts):
    """
    Artifact preparation should not delete already existed artifacts
    """
    global config

    files_stat = {}
    for root, dirs, files in walk(config["artifacts_dir"]):
        for file in files:
            files_stat[file] = c_time(join(root, file))

    command, config = prepare(config)

    for root, dirs, files in walk(config["artifacts_dir"]):
        for file in files:
            assert files_stat[file] == c_time(join(root, file)), "File '{}' was not be changed".format(file)


def test_prepare_test_artifacts_repeat_remake_files(temp_dir, prepare_test_artifacts):
    """
    Remake artifacts if source files was changed
    """
    global config

    new_config = make_basic_artifacts(config, text="New files with new text", add_function=add_from_another_zip)

    files_stat = {}
    for root, dirs, files in walk(config["artifacts_dir"]):
        for file in files:
            files_stat[file] = c_time(join(root, file))

    # wait for file creation date will changed
    sleep(1)

    command, config = prepare(new_config)

    for root, dirs, files in walk(config["artifacts_dir"]):
        for file in files:
            assert files_stat[file] != c_time(join(root, file)), "File '{}' was be changed".format(file)


def test_setup_local_environment_clean_none(temp_dir, prepare_without_local_structure):
    """
    setup_local_test_environment should add new tests folders without --clean option
    """

    global config
    config['clean'] = None
    setup_test_environment(config)
    expected = ["artifacts", 'test-0']
    actual = listdir(config["var_dir"])
    assert sorted(expected) == sorted(actual)
    artifacts_dir_stat = c_time(join(config["var_dir"], 'artifacts'))
    test_dir_stat = c_time(join(config["var_dir"], 'test-0'))

    config["dir_prefix"] = 'test-1'
    setup_test_environment(config)
    actual = listdir(config["var_dir"])
    expected = ["artifacts", 'test-0', 'test-1']
    assert sorted(expected) == sorted(actual)

    assert artifacts_dir_stat == c_time(join(config["var_dir"], 'artifacts'))
    assert test_dir_stat == c_time(join(config["var_dir"], 'test-0'))


def test_setup_local_environment_clean_tests(temp_dir, prepare_without_local_structure):
    """
    setup_local_test_environment should remove tests folders with --clean=tests option
    """
    global config
    config['clean'] = 'tests'
    setup_test_environment(config)
    actual = listdir(config["var_dir"])
    expected = ["artifacts", 'test-0']
    assert sorted(expected) == sorted(actual)
    artifacts_dir_stat = c_time(join(config["var_dir"], 'artifacts'))

    config["dir_prefix"] = 'test-1'
    setup_test_environment(config)
    actual = listdir(config["var_dir"])
    expected = ["artifacts", 'test-1']
    assert sorted(expected) == sorted(actual)

    assert artifacts_dir_stat == c_time(join(config["var_dir"], 'artifacts'))


def test_setup_local_environment_clean_all(temp_dir, prepare_without_local_structure):
    """
    setup_local_test_environment should remove all var dir folder with --clean=all option
    """
    global config
    config['clean'] = 'tests'
    setup_test_environment(config)
    actual = listdir(config["var_dir"])
    expected = ["artifacts", 'test-0']
    assert sorted(expected) == sorted(actual)
    artifacts_dir_stat = c_time(join(config["var_dir"], 'artifacts'))
    sleep(1)

    config["dir_prefix"] = 'test-1'
    setup_test_environment(config)
    actual = listdir(config["var_dir"])
    expected = ["artifacts", 'test-1']
    assert sorted(expected) == sorted(actual)

    assert artifacts_dir_stat == c_time(join(config["var_dir"], 'artifacts'))


def test_init_remote_hosts_clean_none(temp_dir, prepare_remote_structure):
    """
    init_remote_hosts should add new tests folders without --clean option
    """
    ssh = LocalPool(config['ssh'])
    ssh.connect()

    init_remote_hosts(ssh, config)

    home_dir = join(config["ssh"]["home"], '127.0.0.1')
    expected = ["artifacts", 'test-0']
    actual = listdir(home_dir)
    assert sorted(expected) == sorted(actual)
    artifacts_dir_stat = c_time(join(home_dir, 'artifacts'))
    test_dir_stat = c_time(join(home_dir, 'test-0'))

    config["remote"]["suite_var_dir"] = join(config["ssh"]["home"], 'test-1')

    init_remote_hosts(ssh, config)

    expected = ["artifacts", 'test-0', 'test-1']
    actual = listdir(home_dir)
    assert sorted(expected) == sorted(actual)

    assert c_time(join(home_dir, 'artifacts')) == artifacts_dir_stat
    assert test_dir_stat == c_time(join(home_dir, 'test-0'))


def test_init_remote_hosts_clean_tests(temp_dir, prepare_remote_structure):
    """
    init_remote_hosts should remove tests folders with --clean=tests option
    """
    ssh = LocalPool(config['ssh'])
    ssh.connect()

    init_remote_hosts(ssh, config)

    home_dir = join(config["ssh"]["home"], '127.0.0.1')
    expected = ["artifacts", 'test-0']
    actual = listdir(home_dir)
    assert sorted(expected) == sorted(actual)
    artifacts_dir_stat = c_time(join(home_dir, 'artifacts'))

    config["remote"]["suite_var_dir"] = join(config["ssh"]["home"], 'test-1')

    config['clean'] = 'tests'
    init_remote_hosts(ssh, config)

    expected = ["artifacts", 'test-1']
    actual = listdir(home_dir)
    assert sorted(expected) == sorted(actual)

    assert artifacts_dir_stat == c_time(join(home_dir, 'artifacts'))


def test_init_remote_hosts_clean_all(temp_dir, prepare_remote_structure):
    """
    init_remote_hosts should remove all var folders with --clean=all option
    """
    ssh = LocalPool(config['ssh'])
    ssh.connect()

    init_remote_hosts(ssh, config)

    home_dir = join(config["ssh"]["home"], '127.0.0.1')
    expected = ["artifacts", 'test-0']
    actual = listdir(home_dir)
    assert sorted(expected) == sorted(actual)
    artifacts_dir_creation_time = c_time(join(home_dir, 'artifacts'))

    config["remote"]["suite_var_dir"] = join(config["ssh"]["home"], 'test-1')

    config['clean'] = 'all'
    init_remote_hosts(ssh, config)

    expected = ["artifacts", 'test-1']
    actual = listdir(home_dir)
    assert sorted(expected) == sorted(actual)

    assert artifacts_dir_creation_time != c_time(join(home_dir, 'artifacts'))


def test_upload_artifacts(temp_dir, prepare_artifacts_with_ssh_structure):
    """
    upload_artifacts should copy artifacts and unzip archives
    """
    ssh = LocalPool(config['ssh'])
    ssh.connect()

    ssh_home_dir = join(config["ssh"]["home"], '127.0.0.1')

    init_remote_hosts(ssh, config)
    upload_artifacts(ssh, config, prepare_artifacts_result)

    assert sorted(["artifacts", 'test-0']) == sorted(listdir(ssh_home_dir))

    expected_artifacts_dir_files = [
        config['_test_artifacts']["source"]["arch"]["repack_name"],
        config['_test_artifacts']["additional"]["file"]["name"],
        config['_test_artifacts']["additional"]["arch"]["name"]
    ]
    actual_artifacts_files_list = listdir(join(ssh_home_dir, 'artifacts'))
    assert sorted(expected_artifacts_dir_files) == sorted(actual_artifacts_files_list)

    expected_tests_files = [name for name, conf in config["artifacts"].items() if conf.get("remote_unzip", False)]
    actual_tests_files = listdir(join(ssh_home_dir, 'test-0'))
    assert sorted(expected_tests_files) == sorted(actual_tests_files)


def test_repeat_upload_artifacts_same_artifacts(temp_dir, prepare_artifacts_with_ssh_structure):
    """
    repeat usage upload_artifacts should not touch old artifacts
    """
    ssh = LocalPool(config['ssh'])
    ssh.connect()

    ssh_home_dir = join(config["ssh"]["home"], '127.0.0.1')
    art_dir = join(ssh_home_dir, 'artifacts')

    init_remote_hosts(ssh, config)
    upload_artifacts(ssh, config, prepare_artifacts_result)
    previous_art_creation_times = [c_time(join(art_dir, artifact)) for artifact in listdir(art_dir)]

    # don't unzip here twice, because we don't change test directory
    upload_artifacts(ssh, config, [])
    actual_art_creation_times = [c_time(join(art_dir, artifact)) for artifact in listdir(art_dir)]

    assert sorted(previous_art_creation_times) == sorted(actual_art_creation_times)


def test_repeat_upload_artifacts_changed_artifacts(temp_dir, prepare_artifacts_with_ssh_structure):
    """
    repeat usage upload_artifacts with changed artifacts should copy only changed artifacts
    """

    ssh = LocalPool(config['ssh'])
    ssh.connect()

    ssh_home_dir = join(config["ssh"]["home"], '127.0.0.1')
    art_dir = join(ssh_home_dir, 'artifacts')

    init_remote_hosts(ssh, config)
    upload_artifacts(ssh, config, prepare_artifacts_result)
    previous_art_creation_times = dict(
        [(artifact, c_time(join(art_dir, artifact))) for artifact in listdir(art_dir)])
    test_file_path = join(config["artifacts_dir"], config['_test_artifacts']["additional"]["file"]["name"])
    with open(test_file_path, "w") as f:
        f.write("Things changed")
    upload_artifacts(ssh, config, prepare_artifacts_result)
    actual_art_creation_times = [(c_time(join(art_dir, artifact)), artifact) for artifact in listdir(art_dir)]

    for actual_art_creation_time, artifact_name in actual_art_creation_times:
        if artifact_name == config['_test_artifacts']["additional"]["file"]["name"]:
            assert actual_art_creation_time != previous_art_creation_times[artifact_name]
        else:
            assert actual_art_creation_time == previous_art_creation_times[artifact_name]

# TODO: configuration restored from previous where new file not exist

def repeat_upload_changed_artifacts(temp_dir, prepare_artifacts_with_ssh_structure):
    """
    upload artifact
    changing source artifact
    trying to run without --clean
    artifact should be uploaded again
    """
    global config

    ssh = LocalPool(config['ssh'])
    ssh.connect()

    ssh_home_dir = join(config["ssh"]["home"], '127.0.0.1')
    art_dir = join(ssh_home_dir, 'artifacts')

    init_remote_hosts(ssh, config)
    upload_artifacts(ssh, config, prepare_artifacts_result)

    new_file = join(config["artifacts_dir"], "new_file.txt")
    with open(new_file, "w") as f:
        f.write("Things changed")

    config["artifacts"]["source_zip"]["repack"].append("copy {} self:/".format(new_file))
    new_prepare_artifacts_result, config = prepare(config)
    upload_artifacts(ssh, config, new_prepare_artifacts_result)

    expected_files = ['additional_artifact.txt', 'new_file.txt', 'source_artifact.txt',
                      'tiden_repack_original.checksum.sha256']
    with ZipFile(join(art_dir,
                      basename(config["artifacts"]["source_zip"]["path"])), 'r') as repack_zip:
        actual_files_names = [item.filename for item in repack_zip.filelist]
    assert sorted(actual_files_names) == sorted(expected_files)


def test_repeat_upload_tar_artifacts(temp_dir, simple_structure):
    """
    upload and repack tar artifacts
    """
    global config

    ssh = LocalPool(config['ssh'])
    ssh.connect()

    init_remote_hosts(ssh, config)
    upload_artifacts(ssh, config, prepare_artifacts_result)
    not_found = [art for art in config["artifacts"].keys() if not exists(join(config["remote"]["suite_var_dir"], art))]
    assert not_found != [], "Can't find artifacts: {}".format(', '.join(not_found))

    for_repack = ['source_artifact.txt',
                  'tiden_repack_original.checksum.sha256',
                  'second_inner_dir']

    for name, art in config["artifacts"].items():
        assert join(config["remote"]["suite_var_dir"], name) == art["remote_path"]

        actual_dirs_list = listdir(art["remote_path"].replace("remote", "remote/127.0.0.1"))
        expected_dirs_list = for_repack if 'repack' in name else [for_repack[0]]
        assert sorted(actual_dirs_list) == sorted(expected_dirs_list)

