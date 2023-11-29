#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import logging
import paramiko
import jumpssh
from scp import SCPClient
from env import get_envs
from stat import S_ISDIR

logger = logging.getLogger(__name__)

envs = get_envs()

SSH_IP = os.environ.get("KM_IP") or envs["ssh_ip"]
SSH_PORT = os.environ.get("SSH_PORT") or envs["ssh_port"]
SSH_USER = envs.get("ssh_user", "")
SSH_PWD = envs.get("ssh_pwd", "")
CLOUD_SSH_USER = envs.get("cloud_ssh_user", "")
CLOUD_SSH_PWD = envs.get("cloud_ssh_pwd", "")
EDGE_SSH_USER = envs.get("edge_ssh_user", "")
EDGE_SSH_PWD = envs.get("edge_ssh_pwd", "")
EDGE_SSH_HOST = envs.get("edge_ssh_host", "")
EDGE_SSH_PORT = envs.get("edge_ssh_port", 22)
DOCKER_CONTAINER_COMMAND = f"sudo docker ps | grep k8s_agent_cattle | awk '{{print $1}}' | xargs -I {{}} sudo docker exec {{}} bash -c "


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

    def aibox_command(self, cmd, root_password="sfedge\n", timeout=None):
        """
        root_password：以普通用户进入盒子后台，需要切换用户并输入密码
        """
        stdin, stdout, stderr = self.conn.exec_command(cmd, get_pty=True, timeout=timeout)
        stdin.write(root_password)
        stdin.flush()
        result = stdout.read().decode('utf-8')
        error_info = stderr.read().decode('utf-8')
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


class SSH_JUMP:
    def __init__(self, host, port, username, password, timeout=None):
        """
        初始化跳板机
        host, port, username, password：跳板机的登陆信息
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = self.gateway_session()

    def gateway_session(self):
        """
        登陆跳板机
        """
        session = jumpssh.SSHSession(host=self.host, port=int(self.port), username=self.username,
                                     password=self.password, timeout=self.timeout).open(retry=5)

        return session

    def jump_session(self, host, port, username=CLOUD_SSH_USER, password=CLOUD_SSH_PWD, timeout=None):
        """
        通过跳板机登陆到目标主机
        host, port, username, password：目标主机的登陆信息
        """
        session = self.session.get_remote_session(host=host, port=int(port), username=username,
                                                  password=password, timeout=timeout, retry=5)
        return session

    def close(self):
        self.session.close()

    # 通过__enter__和__exit__实现with上下文管理
    def __enter__(self):
        # print("开启远程连接")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # print("关闭远程连接")
        self.close()

"""
def gateway_session(host=SSH_IP, port=SSH_PORT, username=SSH_USER, password=SSH_PWD, timeout=None):
    # 登陆跳板服务器

    session = jumpssh.SSHSession(host=host, port=int(port), username=username,
                                 password=password, timeout=timeout).open()

    return session


def target_session(session, host, port=22, username="root", password="Sangfor@123", timeout=None):
    # 通过跳板登目标服务器
    session = session.get_remote_session(host=host, port=int(port), username=username,
                                         password=password, timeout=timeout)
    return session
"""


def ssh_jump(host=SSH_IP, port=SSH_PORT, username=SSH_USER, password=SSH_PWD):
    """
    默认使用local集群的主机作为跳板机
    """
    ssh_config = {
        "host": host,
        "port": port,
        "username": username,
        "password": password
    }
    ssh_jump = SSH_JUMP(**ssh_config)
    return ssh_jump


def exec_command(ssh_session, command):
    # 登陆服务器后执行命令，不需要输入密码
    try:
        ret = ssh_session.run_cmd(command)
    except Exception as msg:
        # exit_code = ret.exit_code
        print(msg)
        return ["", False]
    response = ret.output
    return [response, True]


def exec_command_with_password(ssh_session, command, root_password="sfedge\n"):
    # 登陆服务器后执行命令, 需要输入密码
    try:
        stdin, stdout, stderr = ssh_session.ssh_client.exec_command(command, get_pty=True)
        stdin.write(root_password)
        stdin.flush()
        response = stdout.read().decode('utf-8')
    except Exception as msg:
        # exit_code = ret.exit_code
        print(msg)
        return ["", False]
    return [response, True]


def get_real_time_data(ssh_client, command, timeout=None):
    """
    获取实时的输出
    """
    stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
    for line in stdout:
        strip_line = line.strip("\n")
        yield strip_line


def get_remote_files(ssh_session, remote_path, local_path):
    """
    将远程服务器上的文件拷贝到被本地
    """
    if not os.path.isfile(remote_path):
        get_remote_folder(ssh_session, remote_path, local_path)
    else:
        ssh_session.get(remote_path, local_path)


def put_local_files(ssh_session, local_path, remote_path):
    """
    将本地文件拷贝到远程服务器上
    """
    if os.path.isdir(local_path):
        put_local_folder(ssh_session, local_path, remote_path)

    else:
        if not os.path.isfile(remote_path):
            file_name = os.path.basename(local_path)
            remote_path = os.path.join(remote_path, file_name)
        ssh_session.put(local_path, remote_path)


def put_local_folder(ssh_session, local_folder, remote_folder):
    """
    将本地文件夹拷贝到远程服务器上
    """
    # 创建远程文件夹
    fold_name = os.path.basename(local_folder)
    remote_folder = os.path.join(remote_folder, fold_name)
    ssh_session.run_cmd("mkdir -p {}".format(remote_folder))
    # 递归上传文件夹中的所有文件和子文件夹
    for item in os.listdir(local_folder):
        local_path = os.path.join(local_folder, item)
        remote_path = os.path.join(remote_folder, item).replace('\\', '/')
        if os.path.isfile(local_path):
            ssh_session.put(local_path, remote_path)
        elif os.path.isdir(local_path):
            put_local_folder(ssh_session, local_path, remote_path)


def get_remote_folder(ssh_session, remote_folder, local_folder):
    """
    将远程服务器上的文件夹拷贝到本地
    """
    sftp = ssh_session.get_sftp_client()

    # 创建本地文件夹
    fold_name = os.path.basename(remote_folder)
    local_folder = os.path.join(local_folder, fold_name)
    os.makedirs(local_folder, exist_ok=True)

    # 递归下载文件夹中的所有文件和子文件夹
    files = sftp.listdir_attr(remote_folder)
    for item in files:
        remote_path = os.path.join(remote_folder, item.filename)
        local_path = os.path.join(local_folder, item.filename)
        if S_ISDIR(item.st_mode):
            get_remote_folder(ssh_session, remote_path, local_path)
        else:
            ssh_session.get(remote_path, local_path)


"""
一些通用的后台查询
"""


def get_edge_hostname(**kw):
    cmd = "hostname"
    with ssh_jump(**kw) as client:
        session = client.session
        hostname = exec_command(session, cmd)[0]
        return hostname


def get_cloud_hostname(**kw):
    cmd = "hostname"
    with ssh_jump() as client:
        session = client.jump_session(**kw)
        hostname = exec_command(session, cmd)[0]
        return hostname
