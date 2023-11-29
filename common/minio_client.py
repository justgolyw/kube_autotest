#!/usr/bin/env python
# -*- coding: utf-8 -*-
import minio
import requests
from pathlib import Path
from datetime import datetime

MINIO_URL = "http://10.113.64.3:32743/minio/webrpc"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36"

file_path = Path(__file__).absolute().parent.parent / "testdata" / "checksum.txt"

USERNAME = "admin"
PASSWORD = "fkxk855dbklrl9f8smhqggp84tc7hcppw8sxrv4bdd88qvddx2ln58"


def minio_login():
    """
    minio用户登录获取token
    """
    json = {
        "id": 1,
        "jsonrpc": "2.0",
        "params": {
            "username": USERNAME,
            "password": PASSWORD
        },
        "method": "Web.Login"
    }
    headers = {
        "User-Agent": USER_AGENT
    }
    response = requests.post(MINIO_URL, json=json, headers=headers)
    assert response.status_code == 200
    token = response.json()["result"]["token"]
    return token


def get_buck_object(token):
    """
    获取bucket中的对象
    """
    json = {
        "id": 1,
        "jsonrpc": "2.0",
        "params": {
            "bucketName": "pipeline-logs",
            "prefix": "pkg/"
        },
        "method": "Web.ListObjects"
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Authorization": "Bearer " + token
    }
    response = requests.post(MINIO_URL, headers=headers, json=json)
    assert response.status_code == 200
    object_list = response.json()["result"]["objects"]
    # 按照修改时间进行排序
    object_list.sort(key=lambda k: k["lastModified"], reverse=True)
    object_name = object_list[0]["name"]
    return object_name


def get_object_url(token, object_name):
    """
    获取run包的url
    """
    json = {
        "id": 1,
        "jsonrpc": "2.0",
        "params": {
            "host": "10.113.64.3:32743",
            "bucket": "pipeline-logs",
            "object": object_name,
            "expiry": 432000
        },
        "method": "Web.PresignedGet"
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Authorization": "Bearer " + token
    }
    response = requests.post(MINIO_URL, headers=headers, json=json)
    assert response.status_code == 200
    address = response.json()["result"]["url"]
    return address


def get_download_link():
    """
    获取run包的下载地址
    """
    token = minio_login()
    object_name = get_buck_object(token)
    url = get_object_url(token, object_name)
    return "http://" + url


class MinioClient(object):
    def __init__(self):
        minio_conf = {
            'endpoint': '10.113.64.3:32743',
            'access_key': USERNAME,
            'secret_key': PASSWORD,
            'secure': False
        }
        self.minioClient = minio.Minio(**minio_conf)

    def get_object_checksum(self, bucket_name="pipeline-logs", prefix="pkg", recursive=True):
        """
        获取最新run包的MD5值
        """
        try:
            objects = self.minioClient.list_objects(bucket_name, prefix=prefix, recursive=recursive)
            obj_list = []
            for obj in objects:
                obj_list.append(obj)
            # 根据修改时间进行排序
            obj_list.sort(key=lambda k: datetime.strftime(k.last_modified, '%Y-%m-%d %H:%M:%S'), reverse=True)
            return obj_list[0].etag
        except Exception as err:
            print(err)


def write_checksum(file_path, content):
    """
    将checksum的值写入文件
    """
    with open(file_path, 'w') as f:
        f.write(content)


def read_checksum(file_path):
    """
    从文件中读取checksum的值
    """
    with open(file_path, 'r') as f:
        checksum = f.read()
    return checksum
