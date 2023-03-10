# Copyright (C) 2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
from system_tools.config import HostTargetConfig, StorageTargetConfig
from system_tools.ssh_terminal import SSHTerminal
from dotenv import load_dotenv

load_dotenv()

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

import ipdb; ipdb.set_trace()

delete_cmd = create_sender_cmd(
    f"""delete_nvme_device {ipu_storage_container_ip} 8080 {host_target_ip} 50051 {pf}"""
)

print('script finished')

