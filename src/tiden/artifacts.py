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

import hashlib
import os.path
import tarfile
from glob import glob
from os import path, mkdir, listdir, remove, walk
from os.path import join, exists, basename
from re import search, sub
from shutil import copyfile, rmtree
from shutil import move, copy, copytree
from zipfile import BadZipfile, ZipFile

import yaml

from .util import log_print, print_red, print_green, calculate_sha256, load_yaml

TIDEN_ARTIFACTS_CONFIG = 'local_artifacts_config.yaml'
TIDEN_REPACK_CHECKSUM_FILE_NAME = 'tiden_repack_original.checksum.sha256'

archive_types = {
    "zip": {
        "pattern": ".zip",
        "open": ZipFile,
        "mode": "r"
    },
    "tar": {
        "pattern": ".tar",
        "open": tarfile.open,
        "mode": "r|"
    },
    "tar_gz": {
        "pattern": ".tar.gz",
        "open": tarfile.open,
        "mode": "r|gz"
    }
}


def prepare(config):
    """
    Find all artifacts
    Copy to artifacts dir
    Repack zip files if needed to
    Create command to unzip zip files on remote host
    Add artifacts information in config

    :return:    tuple(command, new_config)
    """
    artifacts_backup_config_path = join(config["var_dir"], TIDEN_ARTIFACTS_CONFIG)
    previous_artifacts_config = load_yaml(artifacts_backup_config_path)

    artifacts_backup_hashes_path = join(config['var_dir'], 'local_hash_artifacts.yaml')
    artifacts_hashes = load_yaml(artifacts_backup_hashes_path)

    changed_artifacts, current_artifacts = get_changed_artifacts(artifacts_hashes, config)

    if len(changed_artifacts) > 0 or not len(previous_artifacts_config) > 0:
        # dump hashes if artifacts has changed
        yaml.dump(current_artifacts, open(artifacts_backup_hashes_path, 'w'))

    copied_artifacts = copy_artifacts(changed_artifacts, config)

    command, config_changes, artifacts_to_delete = repack_and_get_command_to_unzip(previous_artifacts_config,
                                                                                   copied_artifacts,
                                                                                   config)
    config = apply_changes(config_changes, config)

    backup(previous_artifacts_config,
           copied_artifacts,
           artifacts_backup_config_path,
           config)

    delete_artifacts(artifacts_to_delete)
    return command, config


def apply_changes(config_changes, config):
    """
    Found config changes and apply
    """
    for artifact_name, changes in config_changes.items():
        if 'changes' in changes.keys():
            for key, value in changes['changes'].items():
                config["artifacts"][artifact_name][key] = value
        elif 'previous_config' in changes.keys():
            config["artifacts"][artifact_name] = changes['previous_config']
        config["artifacts"][artifact_name]["path"] = changes["path"]
        config["artifacts"][artifact_name]["remote_path"] = changes["remote_path"]
    return config


def get_changed_artifacts(previous_hashes, config):
    """
    Compare current artifacts hashes with previous ones

    :param previous_hashes:     hashes from previous case run
    :param config
    :return:                    tuple(changed artifacts, found artifacts)
    """
    stream_hash = lambda stream: hashlib.sha256(stream.encode('utf-8')).hexdigest()

    changed_artifacts = []
    curr_artifacts = {}
    for artifact_name in config.get('artifacts', {}).keys():
        if len(previous_hashes) > 0:
            if artifact_name not in previous_hashes:
                print_green("New artifact found {}".format(artifact_name))
                changed_artifacts.append(artifact_name)
            elif previous_hashes[artifact_name] != stream_hash(yaml.dump(config['artifacts'][artifact_name]["glob_path"])):
                print_red("Config changed for artifact {}".format(artifact_name))
                changed_artifacts.append(artifact_name)
        else:
            print_green("New artifact found {}".format(artifact_name))
            changed_artifacts.append(artifact_name)

        # compute current artifacts
        curr_artifacts[artifact_name] = stream_hash(yaml.dump(config['artifacts'][artifact_name]["glob_path"]))

    return changed_artifacts, curr_artifacts


def copy_artifacts(changed_artifacts, config):
    """
    Copy changed artifacts to artifacts directory

    :param changed_artifacts:
    :param config
    :return:                    list(copied artifacts)
    """
    copied_artifacts = []
    for artifact_name in config.get('artifacts', {}).keys():
        # copy artifacts
        pattern = config['artifacts'][artifact_name]['glob_path']

        if pattern.startswith('ftp'):
            continue

        found_files = glob(pattern)
        assert len(found_files) == 1, \
            "Found {} artifacts by pattern {}. Expected: 1".format(len(found_files), pattern)
        file = found_files[0]

        new_file = join(config['artifacts_dir'], basename(file))

        checksum_equals = artifacts_equals(artifact_name,
                                           calculate_sha256(file),
                                           new_file,
                                           config)

        # copy file if it not exists in local var directory
        # or sha256 by file doesn't match with original:
        if artifact_name in changed_artifacts or not checksum_equals:
            print_green("Copied %s" % artifact_name)
            copied_artifacts.append(artifact_name)
            copyfile(file, new_file)
    return copied_artifacts


def artifacts_equals(artifact_name, orig_hash, file, config):
    """
    Compare artifacts with hash from previous

    :param artifact_name:   artifact name
    :param orig_hash:       current artifact hash
    :param file:            copied artifact path
    :param config
    :return:                True - artifacts are equals
                            False - artifacts are different
    """
    checksum_equals = False
    if config['artifacts'][artifact_name].get('repack', False):
        # calculate checksum based on inside checksum file
        # inside checksum file is a artifact config dump

        formats = [".zip", ".tar", ".tar.gz", ".tgz"]
        found_formats = [fmt for fmt in formats if file.endswith(fmt)]
        if not found_formats:
            return checksum_equals
        repack_filename = join(config['artifacts_dir'], basename(file).replace(found_formats[0], '.repack.zip'))

        if path.exists(repack_filename):

            with ZipFile(repack_filename, "r") as repack_file:
                if TIDEN_REPACK_CHECKSUM_FILE_NAME in repack_file.namelist():
                    repack_file.extract(TIDEN_REPACK_CHECKSUM_FILE_NAME, config['artifacts_dir'])
                    sha256_file = join(config['artifacts_dir'], TIDEN_REPACK_CHECKSUM_FILE_NAME)
                    if path.exists(sha256_file):
                        with open(sha256_file, 'r') as checksum_repack:
                            checksum_equals = orig_hash == checksum_repack.read()
                    os.remove(sha256_file)

    elif path.exists(file):
        # calculate checksum based on sha256 of file
        checksum_equals = orig_hash == calculate_sha256(file)
    return checksum_equals


def repack_and_get_command_to_unzip(previous_artifacts_config, copied_artifacts, config):
    """
    Repack zip artifacts
    Execute declared rules (move, copy, remove)

    If artifact used in previous case run then just restore previous artifacts configurations from backup
    Compile command to unzip artifacts on remote hosts

    :param previous_artifacts_config:   previous configuration
    :param copied_artifacts:            list of copied artifacts
    :param config:                      current configuration
    :return:                            tuple(command to unzip, config changes, artifacts ot delete)
    """
    artifacts_to_delete = []
    command = []
    config_changes = {}
    for artifact_name in config.get('artifacts', {}).keys():
        if config['artifacts'][artifact_name]['glob_path'].startswith('ftp'):
            continue

        for source_file in glob(config['artifacts'][artifact_name]['glob_path']):

            # new path for artifact
            new_file = join(config['artifacts_dir'], basename(source_file))
            config_changes[artifact_name] = {}
            if config['artifacts'][artifact_name].get('repack', False):
                # artifact need to repack

                if artifact_name in copied_artifacts:
                    # artifact first time copied

                    # remove repack source file
                    if new_file not in artifacts_to_delete:
                        artifacts_to_delete.append(new_file)

                    new_file, artifacts_changes = repack_artifact(artifact_name,
                                                                  new_file,
                                                                  source_file,
                                                                  config)
                    config_changes[artifact_name]["changes"] = artifacts_changes
                else:
                    # artifact copied previously
                    # restore previous artifact configurations from backup
                    log_print("Restore artifact '{}' configuration".format(artifact_name))
                    previous_config = previous_artifacts_config.get(artifact_name)
                    if previous_config:
                        config_changes[artifact_name]["previous_config"] = previous_config
                        new_file = previous_config["path"]
                    else:
                        print_red("Can't find artifact '{}' configuration. "
                                  "Recommend to run tests with --clean=all option".format(artifact_name))

            # set paths

            log_print("%s -> %s" % (artifact_name, new_file))

            config_changes[artifact_name]['path'] = new_file
            config_changes[artifact_name]['remote_path'] = "{}/{}".format(config['remote']['artifacts_dir'],
                                                                          basename(new_file))
            if config['artifacts'][artifact_name].get('remote_unzip') is True:
                artifact_command, remote_path = _get_command(config, artifact_name,
                                                             config_changes[artifact_name]['remote_path'],
                                                             new_file)
                command.append(artifact_command)

                config_changes[artifact_name]['remote_path'] = remote_path

        if config_changes[artifact_name].get('path') is None:
            log_print("Artifact %s not found" % artifact_name)
            exit(1)
    return command, config_changes, artifacts_to_delete


def repack_artifact(artifact_name, repack_path, source_file, config):
    """
    Repack artifacts and execute rules
    """
    log_print("Repacking '{}'".format(artifact_name))
    repack_data = repack(artifact_name, repack_path,
                         calculate_sha256(source_file),
                         config['tmp_dir'],
                         config['artifacts'][artifact_name]['repack'],
                         config['artifacts_dir'],
                         config["artifacts"])

    # move repack
    artifact_repack_path = join(config['artifacts_dir'], basename(repack_data['new_file']))
    if exists(artifact_repack_path):
        if calculate_sha256(artifact_repack_path) != calculate_sha256(repack_data["new_file"]):
            remove(artifact_repack_path)
            move(repack_data["new_file"], config['artifacts_dir'])
    else:
        move(repack_data["new_file"], config['artifacts_dir'])

    artifact_info = {}
    # update artifact configs after repack
    repack_path = join(config['artifacts_dir'], basename(repack_data['new_file']))
    if len(repack_data.keys()) > 1:
        for repack_key in repack_data.keys():
            if repack_key != 'new_file':
                artifact_info[repack_key] = repack_data[repack_key]

    return repack_path, artifact_info


def _get_command(config, artifact_name, remote_path, local_path):
    """
    Compile command to unzip

    :param config:
    :param artifact_name:
    :param remote_path:     artifact remote host path
    :param local_path:      artifact client path
    :return:                tuple(unzip command, new configuration)
    """
    var_dir = config['remote']['suite_var_dir']
    end_path = "{}/{}".format(var_dir, artifact_name)
    unzip_cmd = "unzip -u -q {} -d {}".format(remote_path, end_path)

    tar_formats = [".tar", '.tar.gz', '.tgz']
    found_formats = [fmt for fmt in tar_formats if local_path.endswith(fmt)]
    if found_formats:
        unzip_cmd = "cd {var}; mkdir {dir_name}; tar -xf {artifact_path} -C {dir_name} --strip-components 1".format(
            var=var_dir,
            dir_name=artifact_name,
            artifact_path=remote_path,
        )

    return unzip_cmd, end_path


def backup(previous_artifacts_config, copied_artifacts, config_backup_path, config):
    """
    backup current artifacts configuration

    :param previous_artifacts_config:
    :param copied_artifacts:
    :param config_backup_path:
    :param config
    """
    if not previous_artifacts_config or copied_artifacts:
        log_print("Backup artifacts configuration")
        yaml.dump(config['artifacts'], open(config_backup_path, 'w'))


def delete_artifacts(artifacts_to_delete):
    """
    Clean up temp files after repack
    :param artifacts_to_delete:
    """
    for artifact_to_delete in artifacts_to_delete:
        # remove old artifact
        if path.isdir(artifact_to_delete):
            rmtree(artifact_to_delete)
        elif path.isfile(artifact_to_delete):
            remove(artifact_to_delete)


def repack(artifact_name, src_path, checksum, work_dir, rules, artifacts_dir, artifacts):
    """
    Repack artifacts and execute rules

    :param src_path:        artifact path
    :param checksum:        artifact checksum
    :param work_dir:        path for artifact extraction
    :param rules:           rules
    :param artifacts_dir:   directory with artifacts
    :param artifacts:       artifacts dict
    :return:                dict(artifacts information)
    """
    dirs_to_delete = []
    try:
        new_zip_file = None
        extract_dir = None
        for _, data in archive_types.items():
            if src_path.endswith(data["pattern"]):
                extract_dir = join(work_dir, basename(src_path).replace(data["pattern"], '_in'))
                mkdir(extract_dir)
                with data["open"](src_path, data["mode"]) as arch:
                    arch.extractall(extract_dir)
                new_zip_file = join(work_dir, basename(src_path).replace(data["pattern"], '.repack.zip'))

        assert new_zip_file is not None, "Can't find unzip operation for {} file".format(basename(src_path))

        # Extract everything
        dirs = []

        # Check directories
        for file in listdir(extract_dir):
            full_path = join(extract_dir, file)
            if path.isdir(full_path):
                dirs.append(full_path)
        self_entry = extract_dir
        if len(dirs) == 1:
            self_entry = dirs[0]

        # execute rules
        for rule in rules:
            args = rule.split(' ')
            args, additional_dirs_to_delete = _parse_args(args,
                                                          work_dir,
                                                          artifacts_dir,
                                                          artifact_name,
                                                          artifacts,
                                                          self_entry)
            dirs_to_delete = dirs_to_delete + additional_dirs_to_delete
            if args[0] == 'delete':
                if path.isdir(args[1]):
                    rmtree(args[1])
                elif path.isfile(args[1]):
                    remove(args[1])
            elif args[0] == 'move':
                if path.isdir(args[1]):
                    move(args[1], args[2])
                elif path.isfile(args[1]):
                    move(args[1], args[2])
            elif args[0] == 'copy':
                if type(args[1]) != type([]):
                    args[1] = [args[1]]
                for src_arg in args[1]:
                    if path.isdir(src_arg):
                        copytree(src_arg, args[2])
                    elif path.isfile(src_arg):
                        copy(src_arg, args[2])
                    else:
                        raise FileNotFoundError(f"can't find {src_arg} referenced in {artifact_name} repack rules")
            elif args[0] == 'mkdir':
                mkdir(args[1])

        results = {
            'new_file': new_zip_file
        }

        # Ignite revision
        for file in glob(join(self_entry, "libs", "ignite-core*.jar")):
            with ZipFile(file, "r") as core:
                core.extract('ignite.properties', self_entry)
                with open(join(self_entry, 'ignite.properties')) as r:
                    for line in r:
                        m = search('^(ignite\.[a-z\.]+)=(.+)', line)
                        if m:
                            key = sub('\.', '_', m.group(1))
                            results[key] = m.group(2)
            break

        # Gridgain revision
        for file in glob(join(self_entry, 'libs', 'gridgain-core*.jar')):
            with ZipFile(file, "r") as core:
                core.extract('gridgain.properties', self_entry)
                with open(join(self_entry, "gridgain.properties")) as r:
                    for line in r:
                        m = search('^(gridgain\.[a-z\.]+)=(.+)', line)
                        if m:
                            key = sub('\.', '_', m.group(1))
                            results[key] = m.group(2)
            break

        # put checksum in archive
        checksum_file_path = path.join(work_dir, TIDEN_REPACK_CHECKSUM_FILE_NAME)
        with ZipFile(new_zip_file, "w") as w:
            for dir_name, subdirs, files in sorted(walk(self_entry)):
                arc_name = dir_name[len(self_entry):]
                if arc_name != '':
                    w.write(
                        dir_name,
                        arcname=arc_name
                    )
                for filename in sorted(files):
                    w.write(
                        path.join(dir_name, filename),
                        arcname=path.join(dir_name, filename)[len(self_entry):]
                    )

            # copy checksum to repack file
            with open(checksum_file_path, 'w') as checksum_file:
                checksum_file.write(checksum)
            w.write(checksum_file_path, TIDEN_REPACK_CHECKSUM_FILE_NAME)

        if path.exists(checksum_file_path):
            remove(checksum_file_path)

        # clean up after
        rmtree(extract_dir)
        for dir_to_delete in dirs_to_delete:
            rmtree(dir_to_delete)

    except (FileNotFoundError, BadZipfile) as e:
        print("Error repacking %s : %s" % (src_path, str(e)))
        raise e
    return results


def _expand_globs(pattern):
    return glob(pattern)


def _parse_args(args, extract_dir, artifacts_dir, current_artifact_name, artifacts, self_entry):
    """
    Going through repack args and replace special syntax
    Special syntax:
        self:[path] - replaced on directory with extracted artifact which would be archived in repack
        $artifact_name$[inner path] - replaced on path for selected artifact
                                        if artifact have remote_unzip property then unpack and take path from there
    :param args:                   repack args
    :param extract_dir:            directory where will be contain unpacked artifacts
    :param artifacts_dir:          directory which contain all artifacts
    :param current_artifact_name:  artifact currently been repacked
    :param artifacts:              list of artifacts where need to find searched $artifact_name$
    :param self_entry:             directory with unpacked artifact which is repacked
    :return:                       processed repack arguments
    """
    new_args = [args[0]]
    dirs_to_delete = []
    for arg_idx in range(1, len(args)):
        new_path = args[arg_idx].replace('self:', self_entry)
        # searching for other artifact name
        found = search('^\$.*\$', new_path)
        if found:
            artifact_name = new_path[found.start() + 1:found.end() - 1]
            if artifact_name == current_artifact_name:
                new_path = args[arg_idx].replace('$'+artifact_name+'$', self_entry)
            else:
                # searching for artifact with similar name
                found_configs = [art_config for name, art_config in artifacts.items() if name == artifact_name]
                if not found_configs:
                    raise FileNotFoundError(f"cant find artifact ${artifact_name}$ referenced in {current_artifact_name} repack rules")

                found_config = found_configs[0]

                other_path = new_path[found.end():] if new_path[found.end():] else ""
                art_path = join(artifacts_dir, basename(found_config['glob_path']))
                if other_path == '':
                    new_path = art_path
                else:
                    # unpack  to temp dir if didn't found inner path
                    if found_config.get('remote_unzip'):
                        arc_file = basename(basename(found_config['glob_path']))
                        found_archive_types = [arc_t for arc_t in archive_types.values() if
                                               arc_file.endswith(arc_t["pattern"])]
                        assert found_archive_types, "Can't open archive {}".format(arc_file)
                        found_archive_type = found_archive_types[0]

                        additional_dir = arc_file.replace(found_archive_type["pattern"], '_additional_in')
                        temp_extract_dir = join(extract_dir, additional_dir)

                        if temp_extract_dir not in dirs_to_delete:
                            dirs_to_delete.append(temp_extract_dir)
                        if not path.exists(temp_extract_dir):
                            mkdir(temp_extract_dir)
                            with found_archive_type["open"](art_path, found_archive_type["mode"]) as old_zip:
                                old_zip.extractall(temp_extract_dir)
                    else:
                        additional_dir = artifact_name + '_additional_in'
                        temp_extract_dir = join(extract_dir, additional_dir)
                        if temp_extract_dir not in dirs_to_delete:
                            dirs_to_delete.append(temp_extract_dir)
                        if not path.exists(temp_extract_dir):
                            mkdir(temp_extract_dir)
                        for art_file in glob(art_path):
                            copy(art_file, temp_extract_dir)
                    if other_path.startswith('/'):
                        other_path = other_path[1:]
                    new_path = path.join(temp_extract_dir, other_path)
            if '*' in new_path:
                new_path = _expand_globs(new_path)

        new_args.append(new_path)
    return new_args, dirs_to_delete

