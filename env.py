#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from pathlib import Path
from common.util import read_yaml
from collections import ChainMap

ENV_PATH = Path(__file__).resolve().parent / "env.yml"

default_envs = {
    "host": "",
    "port": 443,
    "username": "admin",
    "password": "Admin@123",
    "ssh_ip": "",
    "ssh_port": 22345,
    "ssh_user": "root",
    "ssh_pwd": "Sangfor-paas.237",
    "user_cluster_id": "",
    "edge_cluster_id": "",
    "harbor_password": "Harbor-12345"
}


def get_envs_from_yml(env_path=ENV_PATH):
    """
    从yml文件中读取配置信息
    """
    # env_path = Path(__file__).resolve().parent / "env.yml"
    envs = {}
    if env_path.exists():
        envs = read_yaml(env_path)
    return envs


# def get_envs_from_ini(config):
#     """从pytest.ini读取配置信息"""
#     host = config.getini('host')
#     port = config.getini('port')
#     env = {}
#     if host:
#         env["host"] = host
#     if port:
#         env["port"] = port
#     return env


def get_envs():
    """优先从配置文件读取， 没有则读取默认值"""
    yml_envs = get_envs_from_yml()
    envs = ChainMap(yml_envs, default_envs)
    return envs


def get_cloud_node_public_ssh():
    envs = get_envs()

    ssh_ip = envs.get("cloud_ssh_ip", "")
    ssh_port = envs.get("cloud_ssh_port", 22)
    ssh_uname = envs.get("cloud_ssh_user", "root")
    ssh_pwd = envs.get("cloud_ssh_pwd", "Sangfor-paas.237")
    return ssh_ip, ssh_port, ssh_uname, ssh_pwd
