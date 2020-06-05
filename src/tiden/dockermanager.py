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

from os.path import basename
from pprint import PrettyPrinter
from re import match
from uuid import uuid4

from .tidenexception import *
from .util import *
from .sshpool import SshPool


class DockerManager:
    """
    Common actions with docker
    """

    def __init__(self, config, ssh):
        self.ssh: SshPool = ssh
        self.config = config
        self.running_containers = {}
        self.swarm_manager = None
        self.stack_remote_path = None

    def remove_all_containers(self):
        """
        Delete all containers from all hosts
        """
        self.running_containers = {}
        log_print("Remove all running containers")
        cmd = "docker rm -f $(docker ps -aq)"
        self.ssh.exec([cmd])

    def kill_running_containers(self):
        """
        Kill running containers from all hosts
        """
        self.running_containers = {}
        log_print("Kill running containers")
        cmd = "docker kill $(docker ps -q)"
        self.ssh.exec([cmd])

    def prune(self):
        """
        Delete all images/caches/networks from all hosts
        """
        log_print("Clean all host docker data")
        cmd = "docker system prune -fa"
        self.ssh.exec([cmd])

    def clean_host(self):
        """
        Delete all docker data from each host
        :return:
        """
        self.remove_all_containers()
        self.prune()

    def get_containers_info(self, additional_key=''):
        """
        Get information about all running container for all hosts

        :return:    list({
                            "id": container id,
                            "image": image name,
                            "status": container status,
                            "name": container name
                        }, ...)
        """
        res = self.ssh.exec([
            'docker ps --format "{{.ID}} | {{.Image}} | {{.Status}} | {{.Names}} | {{.Ports}}" '+additional_key + ' -a'
        ])
        running_containers = {}
        for host, out in res.items():
            rows = out[0].split("\n")[:-1]
            for row in rows:
                if match(".*\|.*\|.*\|.*\|.*", row):
                    info_list = [item.strip() for item in row.split("|")]
                    info = {
                        "id": info_list[0],
                        'image': info_list[1],
                        'status': info_list[2],
                        'name': info_list[3],
                        'port': info_list[4]
                    }
                    running_containers[host] = running_containers.get(host, []) + [info]
        return running_containers

    def get_all_containers(self, host=None):
        containers = self.get_containers_info(additional_key='-f "status=exited"')
        all_running_containers = self.get_running_containers(host)
        return all_running_containers, containers

    def get_running_containers(self, host=None, predicate=lambda x: True):
        all_running_containers = dict()
        containers = self.get_containers_info()
        # get running containers
        for current_host in containers.keys():
            running_containers = [container for container in containers.get(current_host)
                                  if 'Up' in container.get('status') and predicate(container)]
            if running_containers:
                all_running_containers[current_host] = running_containers

        return all_running_containers if not host else all_running_containers.get(host)

    def remove_containers(self, host=None, name=None, name_pattern=None, image_name=None):
        """
        Remove containers from host
        :param host:                host with expected containers  (otherwise containers will be searching on all hosts)
        :param name:                whole container name
        :param name_pattern:        name pattern
        :return:                    list: removed containers
        """
        hosts = self.get_containers_info()
        removed_containers = []
        for _host, containers in hosts.items():
            if host is not None and _host != host:
                continue
            for container in containers:
                if name is not None and name != container['name']:
                    continue
                elif name_pattern is not None and not match(name_pattern, container['name']):
                    continue
                elif image_name is not None and image_name != container['image']:
                    continue
                log_print("Remove container '{}' on host {}".format(container['name'], _host))
                self.ssh.exec_on_host(_host, ['docker rm -f {}'.format(container['id'])])
                if _host in self.running_containers and container['name'] in self.running_containers[_host]:
                    del self.running_containers[_host][container['name']]
                removed_containers.append(container)
        return removed_containers

    def get_pulled_images(self):
        """
        Get information about all pulled images for all hosts

        :return:    list({
                            "id": "[container_id]",
                            "name": "[repository]:[tag]",
                        }, ...)
        """
        res = self.ssh.exec(['docker images --format "{{.ID}} | {{.Repository}} | {{.Tag}}"'])
        pulled_images = {}
        for host, out in res.items():
            rows = out[0].split("\n")[:-1]
            for row in rows:
                if match(".*\|.*\|.*", row):
                    info_list = [item.strip() for item in row.split("|")]
                    info = {
                        "id": info_list[0],
                        'name': '{}:{}'.format(info_list[1], info_list[2])
                    }
                    pulled_images[host] = pulled_images.get(host, []) + [info]
        return pulled_images

    def remove_images(self, host=None, name=None, name_pattern=None):
        """
        Remove containers from host
        :param host:                host with expected image (otherwise images will be searching on all hosts)
        :param name:                whole image name
        :param name_pattern:        name pattern
        :return:                    list: removed images
        """
        hosts = self.get_pulled_images()
        removed_images = []
        for _host, images in hosts.items():
            if host is not None and _host != host:
                continue
            for image in images:
                if name is not None and name != image['name']:
                    continue
                elif name_pattern is not None and not match(name_pattern, image['name']):
                    continue
                log_print("Remove image '{}' on host {}".format(image['name'], _host))
                self.ssh.exec_on_host(_host, ['docker rmi -f {}'.format(image['id'])])
                removed_images.append(image)
        return removed_images

    def stop(self, host=None, name=None):
        self.ssh.exec_on_host(host, ['docker stop {}'.format(name)])

    def start(self, host=None, name=None):
        self.ssh.exec_on_host(host, ['docker start {}'.format(name)])

    def pause(self, host=None, name=None):
        self.ssh.exec_on_host(host, ['docker pause {}'.format(name)])

    def unpause(self, host=None, name=None):
        self.ssh.exec_on_host(host, ['docker unpause {}'.format(name)])

    def image(self, artifact_name):
        """
        Find image name by artifact name
        """
        artifact = self.config["artifacts"][artifact_name]
        if artifact["type"] == "image_dump":
            path = artifact["glob_path"]
            file_name = basename(path)
            if '.' in file_name:
                image_name = file_name[:file_name.rindex(".")]
            else:
                image_name = file_name
            return image_name

    def build_image(self, host, path, **kwargs):
        cmd = f'docker build {path}'
        if 'tag' in kwargs:
            cmd += f" -t {kwargs['tag']}"
        self.ssh.exec_on_host(host, [cmd])

    def restart_container(self, host, container):
        cmd = f'docker restart {container}'
        self.ssh.exec_on_host(host, [cmd])

    def wait_for_text(self, host, log_file, grep_text, compare, timeout=60, interval=1, strict=True):
        """
        Waiting for expected text in log file

        :param host:        host where collecting all data
        :param log_file:    log file path where need to find expected text
        :param grep_text:   grep pattern for searched file lines
        :param compare:     compare functions which decide searched condition
        :param timeout:     timeout for wait
        :param interval:    time between compare function execute
        :param strict:      throw exception if searched time is up
        :return:            True - condition was correct
                            False - can't wait for condition execute
        """
        cmd = "grep '{}' {}".format(grep_text, log_file)
        end_time = time() + timeout
        while True:
            output = self.ssh.exec_on_host(host, [cmd])[host]
            last_line = output[-1:][0] if output else ""
            if compare(last_line):
                return True
            if time() > end_time:
                if strict:
                    raise AssertionError("Can't wait '{}' on {} in '{}' log".format(grep_text, host, log_file))
                else:
                    return False
            sleep(interval)

    def load_images(self, artifacts_filter=None):
        """
        Unpack image on host from archive

        :param artifacts_filter     str regex to filter artifacts for load
        """
        log_print("Unpack images")
        load_cmd = "docker image load -i {}"
        packed_image_paths = []
        for name, artifact in self.config["artifacts"].items():
            if artifacts_filter is not None:
                if not search(artifacts_filter, name):
                    continue
            if artifact.get("type") != "image_dump":
                continue
            packed_image_paths.append(artifact["remote_path"])
        if not packed_image_paths:
            return
        commands = [load_cmd.format(path) for path in packed_image_paths]
        self.ssh.exec(commands)

    def run(self, image_name, host, **kwargs):
        """
        Run container from image
        Log all container data into log

        :param image_name:      source image name
        :param host:            host where need to run container
        :param kwargs:          tag - custom image tag
                                network - select different network
                                kw_params - custom params (--param_key param_value)
                                commands -  commands list which need to after image start
                                            and declare which process would be main in container
                                volume - map directory in container
                                params - custom params (-i, -t)

        :return:                tuple(Image ID, log file path, image name)
        """

        run_command = "docker run -d {params} {kw_params} {image} {commands}"
        image, params, kw_params, commands, container_name = self.get_params(image_name, kwargs)

        cmd = run_command.format(params=params,
                                 kw_params=kw_params,
                                 image=image,
                                 commands=commands)

        log_print("Running container '{}' from image '{}' on {}".format(container_name, image_name, host))
        output = self.ssh.exec_on_host(host, [cmd])[host]
        if len(output) != 1:
            raise AssertionError("Can't run image {} on host:\n{}".format(image_name, host, "".join(output)))

        last_line = output[-1:][0]
        image_id = last_line.replace("\n", "")
        assert len(image_id) > 30, "Image ID is not correct: '{}'".format(image_id)

        # log container output
        log_file = kwargs.get('log_file', "{}/{}.log".format(self.config["rt"]["remote"]["test_dir"], container_name))
        log_file = self.log_container_output(host, image_id, log_file)

        return image_id, log_file, kwargs["kw_params"]["name"]

    def log_container_output(self, host, image_id, log_file):
        logs_dir = self.config["rt"]["remote"]["test_dir"]
        # log_file = "{}/{}".format(logs_dir, log_file)
        write_logs_command = "cd {log_dir}; " \
                             "nohup " \
                             "  docker logs -f {image} " \
                             "> {log} 2>&1 &".format(log_dir=logs_dir,
                                                     image=image_id,
                                                     log=log_file)
        self.ssh.exec_on_host(host, [write_logs_command])
        return log_file

    def get_params(self, image_name, kwargs):
        params = ""
        kw_params = ""
        commands = ""
        image = image_name

        # setting up unique image name (adding UUID4 at the name end)
        _kw_params = kwargs.get("kw_params", {})
        container_name = kwargs.get("name", f"{sub('/|:', '-', image_name)}-{str(uuid4())[:8]}")

        _kw_params["name"] = container_name
        kwargs["kw_params"] = _kw_params

        if kwargs.get("tag"):
            image = "{}:{}".format(image_name, kwargs["tag"])
        if kwargs.get("network"):
            kw = kwargs.get("kw_params", {})
            kw["network"] = kwargs["network"]
            kwargs["kw_params"] = kw
        if kwargs.get('ports'):
            kwargs['skw_params'] = kwargs.get('skw_params', [])
            for host_port, container_port in kwargs['ports']:
                kwargs['skw_params'].append(('p', '{}:{}'.format(host_port, container_port)))
        if kwargs.get("kw_params"):
            param_list = []
            iter_params = [kwargs.get("kw_params", {}).items(), kwargs.get("skw_params", [])]
            for iter_param in iter_params:
                for key, value in iter_param:
                    special_symbol = '' if len(key) == 1 else '-'
                    param_list.append("{}-{} {}".format(special_symbol, key, value))
            kw_params += ' '.join(param_list)
        if kwargs.get("commands"):
            commands = " ".join(kwargs["commands"])
        if kwargs.get("volume"):
            param = []
            for local_dir, container_dir in kwargs["volume"].items():
                param.append("-v {}:{}".format(local_dir, container_dir))
            kw_params += "{} {}".format(kw_params, " ".join(param))
        if kwargs.get('ekw_params'):
            for k, v in kwargs['ekw_params'].items():
                kw_params += ' --{}={} '.format(k, v)
        if kwargs.get("params"):
            for param in kwargs["params"]:
                params += " -{} ".format(param)

        # if need to redefine entry command by your own
        if kwargs.get('bash_commands', True) and commands:
            commands = 'bash -c "{}"'.format(commands)

        return image, params, kw_params, commands, container_name

    def exec_in_container(self, cmd, container, host=None, log_path=None):
        """
        Execute command into container
        :param cmd:             command
        :param container:       container object
        :return:                command output
        """
        if isinstance(container, str):
            container_id = container
        else:
            container_id = container['id']
            host = container['host']
        exec_cmd = 'docker exec {} bash -c "{}"'.format(container_id, cmd)

        if log_path is not None:
            exec_cmd = 'nohup {} > {} 2>&1 &'.format(exec_cmd, log_path)
        output = self.ssh.exec_on_host(host, [exec_cmd])[host]
        return output[0] if len(output) == 1 else ""

    def _find_host(self, searched_container):
        """
        Find host by container name
        :param searched_container:  container obj
        :return:                    host address
        """
        for host, images in self.running_containers.items():
            for name, image in images.items():
                if image["id"] == searched_container["id"]:
                    return host
        raise AssertionError("Can't find image {} ({}) in running pool".format(searched_container["name"],
                                                                               searched_container["id"]))

    def get_logs(self, container):
        """
        Finding container logs
        :param container:   container onj
        :return:            logs result
        """
        cmd = 'cat {}'.format(container["log"])
        host = self._find_host(container)
        return self.ssh.exec_on_host(host, [cmd])[host]

    def _finds(self, items, condition):
        """
        filter containers by condition
        :param items:       where need to search
        :param condition:   condition to decide
        :return:            found items list
        """
        result = []
        for host, images in items.items():
            for name, image in images.items():
                if condition(image):
                    result.append(image)
        return result

    def find(self, items, condition):
        """
        Find first item which satisfied the condition
        :param items:       where need to search
        :param condition:
        :return:
        """
        result = self._finds(items, condition)
        return result[0] if result else result

    def find_image_by_type(self, type):
        return self.find(self.running_containers, lambda image: image["type"] == type)

    def find_image_by_name(self, name):
        return self.find(self.running_containers, lambda image: image["name"] == name)

    def remove_container(self, container):
        """
        Remove container from host
        :param container:   str - container name
                            dict - container obj
        """
        if isinstance(container, str):
            container = self.find_image_by_name(container)
        self.remove_containers(host=container["host"], name=container["name"])
        del self.running_containers[container["host"]][container["name"]]
        self.remove_unused_volumes()

    def remove_unused_volumes(self):
        self.ssh.exec(['docker volume prune -f'])

    def check_hosts(self):
        """
        Docker on host must have 'overlay' storage driver
        """
        for host in self.ssh.hosts:
            results = self.ssh.exec_on_host(host, ["docker info"])[host][0]
            for line in results.split("\n"):
                if 'Storage Driver' in line:
                    if 'overlay' not in line:
                        raise TidenException("Host '{}' have no 'overlay' docker "
                                             "storage driver ($ docker info -> Storage Driver:)".format(host))
                    else:
                        break

    def _cp(self, host, src_path, dist_path):
        log_print('docker copy {} -> {}'.format(src_path, dist_path), color='debug')
        self.ssh.exec_on_host(host, ['docker cp {} {}'.format(src_path, dist_path)])

    def container_put(self, host, container_name, host_path, container_path):
        """
        Copy file from remote host inside container

        :param ssh:             connection
        :param container_name:  container name
        :param host_path:       remote host path
        :param container_path:  path inside container
        """
        self._cp(host, host_path, '{}:{}'.format(container_name, container_path))

    def container_get(self, host, container_name, container_path, host_path):
        """
        Copy file from container on remote host

        :param ssh:             connection
        :param container_name:  container name
        :param container_path:  path inside container
        :param host_path:       remote host path
        """
        self._cp(host, '{}:{}'.format(container_name, container_path), host_path)

    def ls(self, host, container_name, path):
        out = self.ssh.exec_on_host(host, container_name, ['ls {}'.format(path)])
        files = ' '.join(out).replace('\n', '')
        if not files:
            return []
        files = files.split(' ')
        log_print('LS list: {}'.format(' '.join(files)))
        return [file.strip() for file in files]

    def network_disconnect(self, host=None, container_name=None, network_name=None):
        cmd = 'docker network disconnect -f {} {}'.format(network_name, container_name)
        self.ssh.exec_on_host(host, [cmd])

    def network_connect(self, host=None, container_name=None, network_name=None):
        cmd = 'docker network connect {} {}'.format(network_name, container_name)
        self.ssh.exec_on_host(host, [cmd])

    def create_swarm_network(self, network_name=None, driver=None):
        if driver:
            driver = f'-d {driver}'

        log_print(f'Create docker network {network_name}')
        cmd = f'docker network create {driver} {network_name}'
        network_id_res = self.ssh.exec_on_host(self.swarm_manager, [cmd])
        return network_id_res[0] if network_id_res else None

    def init_swarm(self):
        init_cmd = 'docker swarm init'
        log_print('init swarm', color='debug')
        self.leave_swarm()
        add_manager_init_com = None
        for host in self.ssh.hosts:
            if add_manager_init_com is None:
                self.swarm_manager = host
                swarm_init_res = self.ssh.exec_on_host(host, [init_cmd])
                clear_res = [line.strip() for line in swarm_init_res[host][0].split('\n')]
                assert [line for line in clear_res if 'Swarm initialized' in line],\
                    'Failed to initialize swarm on {}: {}'.format(host, ' '.join(clear_res))
                add_manager_init_com = [line for line in clear_res if line.startswith('docker')]
                assert add_manager_init_com, 'Failed to find join command in init output: {}'.format(' '.join(clear_res))
                add_manager_init_com = add_manager_init_com[0]
                log_print('added swarm manager: {}'.format(host))
            else:
                node_join_res = self.ssh.exec_on_host(host, [add_manager_init_com])
                assert [line for line in node_join_res[host] if 'node joined a swarm' in line], \
                    'Failed to join node {}'.format(host)
                log_print('added swarm worker: {}'.format(host))

    def deploy(self, data, deploy_name='ignite'):
        stack_local_path = join(self.config['rt']['test_module_dir'], 'stack.yaml')
        dump(data, open(stack_local_path, 'w'))
        self.ssh.upload_on_host(self.swarm_manager, [stack_local_path], self.config['rt']['remote']['test_dir'])
        self.stack_remote_path = join(self.config['rt']['remote']['test_dir'], 'stack.yaml')

        cmd = 'docker stack deploy -c {} {}'.format(self.stack_remote_path, deploy_name)
        self.ssh.exec_on_host(self.swarm_manager, [cmd])

    def leave_swarm(self):
        log_print('Leave swarm for all hosts', color='debug')
        cmd = 'docker swarm leave -f'
        res = self.ssh.exec([cmd])

    def create_service(self, host, image_name, **kwargs):
        start_cmd = 'docker service create --name {name} --no-healthcheck {params} {kw_params} {host} {image} {cmd}'

        image, params, kw_params, commands, container_name = self.get_params(image_name, kwargs)
        host_constraint = "--constraint 'node.hostname==lab{}.gridgain.local'".format(host.split('.')[-1:][0])

        start_cmd = start_cmd.format(
            name=container_name,
            params=params,
            kw_params=kw_params,
            host=host_constraint,
            image=image,
            cmd=commands
        )
        start_res = self.ssh.exec_on_host(self.swarm_manager, [start_cmd])
        logs_dir = self.config["rt"]["remote"]["test_dir"]

        running_container = None
        log_file = None

        assert self.wait_for(
            lambda hosts: [con['name'] for con in hosts.get(host, []) if container_name in con['name']],
            lambda: self.get_running_containers()
        ), 'Failed to start container {}'.format(container_name)

        for container in self.get_running_containers()[host]:
            if container_name in container['name']:
                log_file = "{}/{}".format(logs_dir, "{}.log".format(container['name']))
                running_container = container
                write_logs_command = "cd {log_dir}; " \
                                     "nohup " \
                                     "  docker logs -f {container_id} " \
                                     "> {log} 2>&1 &".format(log_dir=logs_dir,
                                                             container_id=container['id'],
                                                             log=log_file)
                self.ssh.exec_on_host(host, [write_logs_command])
                break

        assert log_file is not None or running_container is not None, 'Failed to find running container'
        return running_container['id'], log_file, running_container['name']

    def wait_for(self, condition, action=lambda: None, timeout=30, interval=1, failed=None):
        end_time = time() + timeout
        while True:
            result = action()
            if condition(result):
                return True
            elif failed is not None and failed(result):
                return False

            if time() > end_time:
                return False
            sleep(interval)

    def check_docker_on_hosts(self, hosts):
        docker_ps_out = ['CONTAINER', 'ID', 'IMAGE', 'COMMAND', 'CREATED', 'STATUS', 'PORTS', 'NAMES']
        hosts_with_docker = []
        if not isinstance(hosts, list):
            hosts = [hosts]

        for host in hosts:
            results = self.ssh.exec_on_host(host, ["docker ps"])[host][0]
            if len([header_column for header_column in docker_ps_out if header_column in results]) == len(docker_ps_out):
                hosts_with_docker.append(host)

        return hosts_with_docker

    def print_and_terminate_containers(self, need_stop=False):
        def print_warning(running, stop):
            if running:
                log_print('Found running docker containers:', color='red')
                log_print((self.pp.pformat(running)))
            if stop:
                log_print('Found stop docker containers:', color='red')
                log_print(self.pp.pformat(stop))

        running, stop = self.get_all_containers()
        self.pp = PrettyPrinter()
        print_warning(running, stop)
        if running:
            if need_stop:
                log_print('Going to terminate those dockers containers!', color='red')
                self.kill_running_containers()
                running, _ = self.get_all_containers()
                if not len(running):
                    log_print('all containers removed successfully', color='green')
                else:
                    log_print('There are still some containers on hosts', color='red')
                    print_warning(running, None)
                    return len(running)
            else:
                return len(running)
        return -1

