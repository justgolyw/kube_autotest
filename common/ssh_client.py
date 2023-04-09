#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import logging
import paramiko
from scp import SCPClient

logger = logging.getLogger(__name__)

# SSH_IP = os.environ.get("KM_IP") or "10.113.72.93"
SSH_IP = os.environ.get("KM_IP") or "10.113.71.18"
SSH_PORT = os.environ.get("SSH_PORT") or 22345
DOCKER_CONTAINER_COMMAND = f"docker ps | grep k8s_agent_cattle | awk '{{print $1}}' | xargs -I {{}} docker exec {{}} bash -c"


class SSH:
    """
    Paramiko 远程连接操作
    """

    def __init__(self, host, port, username, password, timeout=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.conn = self.ssh_conn()

    def ssh_conn(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                self.host, self.port, self.username, self.password,
                timeout=self.timeout, banner_timeout=self.timeout
            )
        except Exception as e:
            raise e
        return ssh

    def exec_command(self, cmd, timeout=None):
        """
        执行cmd指令
        :param timeout:
        :param cmd:
        :return:
        """
        stdin, stdout, stderr = self.conn.exec_command(cmd, timeout=timeout)
        result = stdout.read().decode('utf-8').strip()
        error_info = stderr.read().decode('utf-8').strip()
        if not result and error_info:
            return [error_info, False]
        return [result, True]

    # def aibox_command(self, cmd, root_password="sfedge\n", timeout=None):
    #     """
    #     root_password：以普通用户进入盒子后台，需要切换用户并输入密码
    #     """
    #     stdin, stdout, stderr = self.conn.exec_command(cmd, get_pty=True, timeout=timeout)
    #     stdin.write(root_password)
    #     stdin.flush()
    #     result = stdout.read().decode('utf-8')
    #     error_info = stderr.read().decode('utf-8')
    #     if not result and error_info:
    #         return [error_info, False]
    #     return [result, True]

    def aibox_command(self, cmd, timeout=None):
        """
        执行cmd指令
        :param timeout:
        :param cmd:
        :return:
        """
        stdin, stdout, stderr = self.conn.exec_command(cmd, timeout=timeout)
        result = stdout.read().decode('utf-8').strip()
        error_info = stderr.read().decode('utf-8').strip()
        if not result and error_info:
            return [error_info, False]
        return [result, True]

    def send_command(self, cmd, timeout=None):
        try:
            _, stdout, stderr = self.conn.exec_command(cmd, timeout=timeout)
            stderr = stderr.read().strip()
        except Exception:
            raise Exception
        result = str(stdout.read().strip(), encoding="utf-8")
        if not result and stderr:
            # 有些命名的输出结果在error里面
            result = stderr
            # raise ValueError("exec command error: %s", stderr)

        if not isinstance(result, str):
            result = ""
        return result

    def send_curl(self, url, is_file=False):
        cmd = "curl " + url
        if is_file:
            cmd = "cd /root/download && curl -O {} --retry 3 --retry-delay 1" \
                  "; rm -rf /root/download/*".format(url)
        return self.send_command(cmd)

    def get_real_time_data(self, cmd, timeout=None):
        """
        获取实时的输出
        """
        try:
            stdin, stdout, stderr = self.conn.exec_command(cmd, timeout=timeout)
            for line in stdout:
                strip_line = line.strip("\n")
                yield strip_line
        except Exception as e:
            raise e

    def get_remote_files(self, remote_files, local_path, **kwargs):
        """将远端服务器上的文件拷贝到本地"""
        with SCPClient(self.conn.get_transport()) as cp:
            if isinstance(remote_files, list):
                for remote_file in remote_files:
                    cp.get(remote_file, local_path, **kwargs)
            elif isinstance(remote_files, str):
                cp.get(remote_files, local_path, **kwargs)
            else:
                raise TypeError(f"'remote_files'类型错误.")
            logger.info(f"拷贝文件到 {local_path} 完成!")

    def put_local_files(self, local_files, remote_path, **kwargs):
        """将本地文件拷贝到远端服务器上"""
        with SCPClient(self.conn.get_transport()) as cp:
            cp.put(local_files, remote_path, **kwargs)
            logger.info(f"拷贝文件({local_files}) 至 {remote_path} 完成!")

    # 通过__enter__和__exit__实现with上下文管理
    def __enter__(self):
        print("开启远程连接")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("关闭远程连接")
        self.conn.close()


def admin_ssh_client(host=SSH_IP, port=SSH_PORT, username="root", password="Sangfor-paas.237"):
    """
    建立ssh连接,进入管理集群后台
    :return: ssh client
    """
    ssh_config = {
        "host": host,
        "port": port,
        "username": username,
        "password": password
    }
    sshClient = SSH(**ssh_config)
    return sshClient


def user_ssh_client(host, port=22, username="root", password="Sangfor-paas.237"):
    """
    建立ssh连接,进入用户集群后台
    :return: ssh client
    """
    ssh_config = {
        "host": host,
        "port": port,
        "username": username,
        "password": password
    }
    sshClient = SSH(**ssh_config)
    return sshClient