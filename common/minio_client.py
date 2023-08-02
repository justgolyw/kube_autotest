#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from datetime import datetime
import requests
import minio
# from minio.error import MinioException
from common.env import get_envs_from_yml

envs = get_envs_from_yml()
minio_host = envs.get("minio_host", "")
minio_port = envs.get("minio_port", "")
minio_uname = envs.get("minio_uname", "")
minio_pwd = envs.get("minio_pwd", "")

minio_url = f"http://{minio_host}:{minio_port}/webrpc"
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36"


def minio_login():
    """
    minio用户登录获取token
    """
    json = {
        "id": 1,
        "jsonrpc": "2.0",
        "params": {
            "username": minio_uname,
            "password": minio_pwd
        },
        "method": "Web.Login"
    }
    headers = {
        "User-Agent": user_agent
    }
    response = requests.post(minio_url, json=json, headers=headers)
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
        "User-Agent": user_agent,
        "Authorization": "Bearer " + token
    }
    response = requests.post(minio_url, headers=headers, json=json)
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
    host = f"{minio_host}:{minio_port}"
    json = {
        "id": 1,
        "jsonrpc": "2.0",
        "params": {
            "host": host,
            "bucket": "pipeline-logs",
            "object": object_name,
            "expiry": 432000
        },
        "method": "Web.PresignedGet"
    }
    headers = {
        "User-Agent": user_agent,
        "Authorization": "Bearer " + token
    }
    response = requests.post(minio_url, headers=headers, json=json)
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


def write_checksum(file_path, content):
    """
    将checksum的值写入文件
    """
    with open(file_path, 'w', encoding="utf-8") as f:
        f.write(content)


def read_checksum(file_path):
    """
    从文件中读取checksum的值
    """
    with open(file_path, 'r', encoding="utf-8") as f:
        checksum = f.read()
    return checksum


# class MinioClient(object):
#     def __init__(self):
#         minio_conf = {
#             'endpoint': f"{minio_host}:{minio_port}",
#             'access_key': minio_uname,
#             'secret_key': minio_pwd,
#             'secure': False
#         }
#         self.minioClient = minio.Minio(**minio_conf)
#
#     def get_object(self, bucket_name="pipeline-logs", prefix="pkg", recursive=True):
#         """
#         获取最新的run包
#         """
#         try:
#             objects = self.minioClient.list_objects(bucket_name, prefix=prefix, recursive=recursive)
#             obj_list = []
#             for obj in objects:
#                 obj_list.append(obj)
#             # 根据修改时间进行排序
#             obj_list.sort(key=lambda k: datetime.strftime(k.last_modified, '%Y-%m-%d %H:%M:%S'), reverse=True)
#             return obj_list[0]
#         except Exception as err:
#             print(err)
#
#     def get_object_url(self, bucket_name="pipeline-logs"):
#         """
#         获取最新的run包下载链接
#         """
#         try:
#             object_name = self.get_object().object_name
#             object_url = self.minioClient.presigned_get_object(bucket_name, object_name)
#             return object_url
#         except Exception as err:
#             print(err)
#
#     def get_object_checksum(self):
#         """
#         获取最新的run包checksum
#         """
#         try:
#             object = self.get_object()
#             return object.etag
#         except Exception as err:
#             print(err)

class MinioClient(Minio):
    def __init__(self, endpoint=f"{minio_host}:{minio_port}",
                 access_key=minio_uname, secret_key=minio_pwd, secure=False):
        super().__init__(endpoint=endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

    def get_run_object(self, bucket_name="pipeline-logs", prefix="pkg", recursive=True):
        """
        获取最新的run包
        """
        try:
            objects = self.list_objects(bucket_name, prefix=prefix, recursive=recursive)
            obj_list = []
            for obj in objects:
                obj_list.append(obj)
            # 根据修改时间进行排序
            obj_list.sort(key=lambda k: datetime.strftime(k.last_modified, '%Y-%m-%d %H:%M:%S'), reverse=True)
            return obj_list[0]
        except Exception as err:
            raise err

    def get_run_url(self):
        """
        获取最新的run包下载链接
        """
        try:
            run_object = self.get_run_object()
            bucket_name = run_object.bucket_name
            object_name = run_object.object_name
            object_url = self.presigned_get_object(bucket_name, object_name)
            return object_url
        except Exception as err:
            raise err

    def get_run_checksum(self):
        """
        获取最新的run包checksum
        """
        try:
            run_object = self.get_run_object()
            return run_object.etag
        except Exception as err:
            raise err