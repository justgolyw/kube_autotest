#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import pymysql
import subprocess
import glob
import json
import time

DATABASE = os.environ.get("DATABASE") or 'node_pool'
SINGLE_WORKER = 'gw99'
CLOUD_TABLE = "cloud"
EDGE_TABLE = "edge"
GATEWAY_TABLE = "gateway"
NODE_TABLE = "vm_pool"
END_EQUIPMENT_TABLE = "end_equipment"


class VMPoolDriver(object):
    def __init__(self):
        self.db_host = os.environ.get("DB_HOST") or "10.113.78.126"
        self.db_port = os.environ.get("DB_PORT") or 3306
        self.db_user = os.environ.get("DB_USER") or "root"
        self.db_pass = os.environ.get("DB_PASS") or "123456"

    def _get_connection(self):
        connection = pymysql.connect(host=self.db_host,
                                     port=int(self.db_port),
                                     user=self.db_user,
                                     password=self.db_pass,
                                     db=DATABASE,
                                     charset='utf8mb4',
                                     cursorclass=pymysql.cursors.DictCursor)
        return connection

    def _exec(self, conn, sql, check=0):
        with conn.cursor() as cursor:
            cursor.execute(sql)
            data = cursor.fetchall()
            if check != 0:
                assert check == cursor.rowcount
        return data

    def occupy_vms(self, number=1, arch=""):
        """
        获取公网ip
        获取容器化的公网ip
        """
        if arch == "":
            arch = os.environ.get("ARCHITECTURE") or "ARCH_AMD"

        if arch == "ARCH_AMD":
            ips = []
            for i in range(number):
                try:
                    ips.append(applyNodeContainer())
                except Exception as e:
                    raise e
            print("ips:", ips)
            return ips


def applyNodeContainer():
    # 获取并发执行时的 worker id  xdist 插件变量
    worker = os.environ.get("PYTEST_XDIST_WORKER") or SINGLE_WORKER

    # 申请创建容器化节点，并保存节点 ip 信息到指定目录
    outputDir = "/caas/ips/" + worker + time.strftime("%d%H%M%S", time.localtime(time.time()))
    cmd = 'ansible-playbook /caas/docker-in-docker/playbook/docker.yml -e ' \
          '"cluster_node_yaml_file=/caas/docker-in-docker/caas-base/template_applyOneNode.yaml" -e ' \
          '"apply_to_kubemanager=false" -e "container_info_dir={dir}"'.format(dir=outputDir)
    ret = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", timeout=300)
    if ret.returncode != 0:
        raise Exception(ret)

    path = outputDir + "/ips_connect*.json"
    ipFiles = glob.glob(path)
    if len(ipFiles) == 0:
        raise Exception("ip file not exist. file path: " + path)
    with open(ipFiles[0], 'r') as f:
        jsonStr = f.read()
    try:
        ipData = json.loads(jsonStr)
    except Exception as e:
        raise Exception("json loads err. file path: " + path + " json str: " + jsonStr)
    if ipData[0].get("connected") != "True":
        raise Exception("node connected fail. file path: " + path + " json str: " + jsonStr)
    if not ipData[0].get("ip"):
        raise Exception("failed on get ip. file path: " + path + " ipData dict: " + str(ipData))

    return ipData[0]["ip"]
