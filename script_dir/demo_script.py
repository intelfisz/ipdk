# Copyright (C) 2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

#set config
STORAGE_TARGET_USERNAME = ""
STORAGE_TARGET_PASSWORD = ""
STORAGE_TARGET_IP_ADDRESS = ""

HOST_TARGET_USERNAME = ""
HOST_TARGET_PASSWORD = ""
HOST_TARGET_IP_ADDRESS = ""

IPU_STORAGE_CONTAINER_IP = "200.1.1.3"
STORAGE_TARGET_IP = "200.1.1.2"  # Address visible from IPU side.





from paramiko.client import AutoAddPolicy, SSHClient

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
        return (
            None if cmd.rstrip().endswith("&") else stdout.read().decode().rstrip("\n")
        )


class StorageTargetConfig:
    def __init__(self):
        self.username = STORAGE_TARGET_USERNAME
        self.password = STORAGE_TARGET_PASSWORD
        self.ip_address = STORAGE_TARGET_IP_ADDRESS
        self.port = 22


class HostTargetConfig:
    def __init__(self):
        self.username = HOST_TARGET_USERNAME
        self.password = HOST_TARGET_PASSWORD
        self.ip_address = HOST_TARGET_IP_ADDRESS
        self.port = 22




def get_docker_containers_id_from_docker_image_name(terminal, docker_image_name):
    out = terminal.execute(
        f'sudo docker ps | grep "{docker_image_name}"'
    ).splitlines()
    return [line.split()[0] for line in out]

ipu_storage_container_ip = IPU_STORAGE_CONTAINER_IP
storage_target_ip = STORAGE_TARGET_IP
host_target_ip = HostTargetConfig().ip_address

print('Script is starting')
linkpartner_terminal = SSHTerminal(StorageTargetConfig())
try:
    cmd_sender_id = get_docker_containers_id_from_docker_image_name(linkpartner_terminal, "cmd-sender")[0]
except IndexError:
    raise Exception("cmd sender is not running")

# all this things shall run in host target so you can run it where you want

# command sender is in lp so you need docker ip
# and then this command should be send to cmd sender


def create_sender_cmd(cmd):
    return f"""sudo docker exec {cmd_sender_id} bash -c 'source /scripts/disk_infrastructure.sh; export PYTHONPATH=/; """ \
           f"""{cmd}""" \
           """ '"""


# start operation on cmd_sender

pf_cmd = create_sender_cmd(f"""create_nvme_device {ipu_storage_container_ip} 8080 {host_target_ip} 50051 0 0""")
pf = linkpartner_terminal.execute(pf_cmd)

create_subsystem_cmd = create_sender_cmd(
    f"""create_and_expose_sybsystem_over_tcp {storage_target_ip} nqn.2016-06.io.spdk:cnode0 4420"""
)
linkpartner_terminal.execute(create_subsystem_cmd)


create_ramdrive_cmd = create_sender_cmd(
    f"""create_ramdrive_and_attach_as_ns_to_subsystem {storage_target_ip} Malloc0 16 nqn.2016-06.io.spdk:cnode0"""
)
malloc0 = linkpartner_terminal.execute(create_ramdrive_cmd)

# todo check
attach_cmd = create_sender_cmd(
    f"""attach_volume {ipu_storage_container_ip} "{pf}" "{malloc0}" nqn.2016-06.io.spdk:cnode0 {storage_target_ip} 4420"""
)
linkpartner_terminal.execute(attach_cmd)

delete_cmd = create_sender_cmd(
    f"""delete_nvme_device {ipu_storage_container_ip} 8080 {host_target_ip} 50051 {pf}"""
)
linkpartner_terminal.execute(delete_cmd)

print("Script finish successfully")
