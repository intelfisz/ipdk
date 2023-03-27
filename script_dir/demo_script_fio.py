# Copyright (C) 2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
from dotenv import load_dotenv
load_dotenv()
from paramiko.client import AutoAddPolicy, SSHClient
from abc import ABC, abstractmethod


STORAGE_DIR_PATH = "ipdk/build/storage"
DEFAULT_NQN = "nqn.2016-06.io.spdk:cnode0"
DEFAULT_SPDK_PORT = 5260
DEFAULT_NVME_PORT = 4420
DEFAULT_SMA_PORT = 8080
DEFAULT_QMP_PORT = 5555
DEFAULT_HOST_TARGET_SERVICE_PORT_IN_VM = 50051
DEFAULT_MAX_RAMDRIVE = 64
DEFAULT_MIN_RAMDRIVE = 1


class SSHTerminal:
    """A class used to represent a session with an SSH server"""

    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.client = SSHClient()

        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(AutoAddPolicy)
        self.client.connect(
            config.ip_address,
            config.port,
            config.username,
            config.password,
            *args,
            **kwargs
        )

    def execute(self, cmd, timeout=20):
        """Simple function executes a command on the SSH server
        Returns list of the lines output
        """
        _, stdout, stderr = self.client.exec_command(cmd, timeout=timeout)
        #if stdout.channel.recv_exit_status():
        #    raise CommandException(stderr.read().decode())
        # if command is executed in the background don't wait for the output
        return (
            None if cmd.rstrip().endswith("&") else stdout.read().decode().rstrip("\n")
        )


class BaseConfig(ABC):
    load_dotenv()

    @abstractmethod
    def __init__(self):
        pass

    def _getenv(self, env_name, alternative=None):
        env = os.getenv(env_name)
        return env if env else alternative


class TestConfig(BaseConfig):
    def __init__(self):
        self.spdk_port = self._getenv("SPDK_PORT", DEFAULT_SPDK_PORT)
        self.nvme_port = self._getenv("NVME_PORT", DEFAULT_NVME_PORT)
        self.qmp_port = self._getenv("QMP_PORT", DEFAULT_QMP_PORT)
        self.max_ramdrive = self._getenv("MAX_RAMDRIVE", DEFAULT_MAX_RAMDRIVE)
        self.min_ramdrive = self._getenv("MIN_RAMDRIVE", DEFAULT_MIN_RAMDRIVE)
        self.debug = self._getenv("DEBUG", "FALSE")
        self.nqn = self._getenv("NQN", DEFAULT_NQN)
        self.cmd_sender_platform = self._getenv("CMD_SENDER_PLATFORM", "ipu")


class BasePlatformConfig(BaseConfig):
    def __init__(self, platform_name):
        self._platform_name = platform_name
        self.username = self._get_platform_property("USERNAME")
        self.password = self._get_platform_property("PASSWORD")
        self.ip_address = self._get_platform_property("IP_ADDRESS")
        self.port = self._get_platform_property("PORT")
        self.workdir = os.getenv(
            "_".join([platform_name, "WORKDIR"]),
            f"/home/{self.username}/ipdk_tests_workdir",
        )

    @property
    def storage_dir(self):
        return os.path.join(self.workdir, STORAGE_DIR_PATH)

    def _get_platform_property(self, property_name):
        return self._getenv("_".join([self._platform_name, property_name]))


class MainPlatformConfig(BasePlatformConfig):
    def __init__(self, platform_name):
        username = self._getenv("_".join([platform_name, "USERNAME"]))
        super().__init__(platform_name) if username else super().__init__(
            "MAIN_PLATFORM"
        )


class StorageTargetConfig(MainPlatformConfig):
    def __init__(self):
        super().__init__("STORAGE_TARGET")


class IPUStorageConfig(MainPlatformConfig):
    def __init__(self):
        super().__init__("IPU_STORAGE")
        self.sma_port = self._getenv("SMA_PORT", DEFAULT_SMA_PORT)


class HostTargetConfig(MainPlatformConfig):
    def __init__(self):
        super().__init__("HOST_TARGET")
        share_dir_path = self._getenv("SHARE_DIR_PATH", "shared")
        self.vm_share_dir_path = os.path.join(self.workdir, share_dir_path)
        self.host_target_service_port_in_vm = self._getenv(
            "HOST_TARGET_SERVICE_PORT_IN_VM", DEFAULT_HOST_TARGET_SERVICE_PORT_IN_VM
        )




def get_docker_containers_id_from_docker_image_name(terminal, docker_image_name):
    out = terminal.execute(
        f'sudo docker ps | grep "{docker_image_name}"'
    ).splitlines()
    return [line.split()[0] for line in out]

ipu_storage_container_ip = os.getenv("IPU_STORAGE_CONTAINER_IP")
storage_target_ip = os.getenv("STORAGE_TARGET_IP")
host_target_ip = HostTargetConfig().ip_address

print('Script is starting')
linkpartner_terminal = SSHTerminal(StorageTargetConfig())
cmd_sender_id = get_docker_containers_id_from_docker_image_name(linkpartner_terminal, "cmd-sender")[0]


# all this things shall run in host target so you can run it where you want

# command sender is in lp so you need docker ip
# and then this command should be send to cmd sender


def create_sender_cmd(cmd):
    return f"""sudo docker exec {cmd_sender_id} bash -c 'source /scripts/disk_infrastructure.sh; export PYTHONPATH=/; """ \
           f"""{cmd}""" \
           """ '"""


# start operation on cmd_sender

import ipdb; ipdb.set_trace()
pf_cmd = create_sender_cmd(f"""create_nvme_device {ipu_storage_container_ip} 8080 {host_target_ip} 50051 0 0""")
pf = linkpartner_terminal.execute(pf_cmd)

import ipdb; ipdb.set_trace()
create_subsystem_cmd = create_sender_cmd(
    f"""create_and_expose_sybsystem_over_tcp {storage_target_ip} nqn.2016-06.io.spdk:cnode0 4420"""
)
linkpartner_terminal.execute(create_subsystem_cmd)
import ipdb; ipdb.set_trace()

create_ramdrive_cmd = create_sender_cmd(
    f"""create_ramdrive_and_attach_as_ns_to_subsystem {storage_target_ip} Malloc0 16 nqn.2016-06.io.spdk:cnode0"""
)
malloc0 = linkpartner_terminal.execute(create_ramdrive_cmd)
import ipdb; ipdb.set_trace()

# todo check
attach_cmd = create_sender_cmd(
    f"""attach_volume {ipu_storage_container_ip} "{pf}" "{malloc0}" nqn.2016-06.io.spdk:cnode0 {storage_target_ip} 4420"""
)
linkpartner_terminal.execute(attach_cmd)

import ipdb; ipdb.set_trace()


cmd = f"""grpc_cli call {host_target_ip}:50051 RunFio""" \
      f""" "diskToExercise: {{ deviceHandle: '{pf}' volumeId: '{malloc0}' }} fioArgs: """ \
      f"""'{{\\"rw\\":\\"randrw\\", \\"runtime\\":1, \\"numjobs\\": 1, \\"time_based\\": 1, """ \
      f"""\\"group_reporting\\": 1 }}'" """
fio_cmd = create_sender_cmd(
    cmd
)
fio = linkpartner_terminal.execute(fio_cmd)

import ipdb; ipdb.set_trace()
delete_cmd = create_sender_cmd(
    f"""delete_nvme_device {ipu_storage_container_ip} 8080 {host_target_ip} 50051 {pf}"""
)

print(fio)
print('script finished')

