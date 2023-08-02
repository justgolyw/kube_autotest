#!/usr/bin/env python
# -*- coding: utf-8 -*-
import base64
import os
import random
import string
import tarfile
import yaml


# 产生随机IP
def rand_ip():
    ip = ""
    for i in range(3):
        ip += str(random.randint(0, 255)) + "."
    return ip + str(random.randint(0, 255))


def rtsp_num():
    ip_1 = random.randint(0, 255)
    ip_2 = random.randint(0, 255)
    rtsp = f'rtsp://10.20.' + str(ip_1) + '.' + str(ip_2)
    return rtsp


def random_num():
    return random.randint(0, 1000)


def random_str():
    return 'test-{0}-{1}'.format(random_num(), random_num())


def user_name():
    return 'test_{0}'.format(random_num())


def user_password():
    return 'Test@123-{0}'.format(random_num())


def random_port():
    return random.randint(10000, 65536)


# 生成含有数字和英文字母的字符串
def generate_random_str(length):
    random_char_list = []
    for _ in range(length):
        random_char = random.choice(string.ascii_letters + string.digits)
        random_char_list.append(random_char)
    random_string = ''.join(random_char_list)
    return random_string


# 生成指定长度的集群名字
def cluster_name(length):
    return generate_random_str(length).lower()


def packing_targz(src_path, file_name):
    """
     一次性打包整个根目录为tar.gz。空子目录会被打包。
     逐个添加文件打包，未打包空子目录。可过滤文件。
     如果只打包不压缩，将"w:gz"参数改为"w:"或"w"即可。
     """
    if os.path.exists(file_name):
        os.remove(file_name)
    with tarfile.open(file_name, "w:gz") as tar:
        tar.add(src_path, arcname=os.path.basename(src_path))


def update_dict(dict1, dict2):
    """
    更新嵌套的字典
    """
    for key, value in dict2.items():
        if isinstance(value, dict):
            dict1[key].update(value)
        else:
            dict1.update({key: value})


def base64_encode(s1):
    """
    base64 编码
    :param s1: 编码前的字符
    :return:
    """
    return bytes.decode(base64.b64encode(s1.encode("utf-8")))


def base64_decode(s1):
    """
    base64 解码
    :param s1: 解码前的字符
    :return:
    """
    return bytes.decode(base64.b64decode(s1.encode("utf-8")))


def read_yaml(yaml_path):
    """
    读取yaml文件
    :param yaml_path:
    :return:
    """
    with open(yaml_path) as f:
        data = yaml.safe_load(f.read())
    return data


def write_yaml(yaml_path, content):
    """
    将content写入yaml文件
    :param yaml_path:
    :param content:
    :return:
    """
    with open(yaml_path, 'w') as f:
        f.write(content)


def sink_ip():
    ip_1 = random.randint(0, 255)
    ip_2 = random.randint(0, 255)
    sink_ip = '192.168.' + str(ip_1) + '.' + str(ip_2)
    return sink_ip


class DictToObject(dict):
    """
    将字典转化为为对象，dict按点方式取值
    a = {
            "x": 123,
            "y": "hello"
        }
        print(a.x)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getattr__(self, name):
        value = self[name]
        if isinstance(value, dict):
            value = DictToObject(value)
        elif isinstance(value, list):
            value = [DictToObject(item) if isinstance(item, dict) else item for item in value]
        return value
