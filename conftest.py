#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import os
import time
import yaml
import pytest
import requests
import urllib3
from common import rancher
from common.comm import ARCH_AMD
from common.comm import wait_until
from common.rancher import ApiError
from common.tp_client import TP
from kubernetes.client import ApiClient, Configuration
from kubernetes.config.kube_config import KubeConfigLoader
from common.util import user_name, packing_targz, random_str
from common.vm_pool import VMPoolDriver, occupy_cloud_pods, occupy_edge_pods
from steps.cluster import clusters
from steps.cluster.clusters import wait_for_cluster_active
from steps.cluster.comm import get_cluster_kwargs, get_edge_cluster_kwargs
from steps.cluster.comm import get_node_kwargs, get_edge_node_kwargs
from steps.node import nodes
from filelock import FileLock
from env import get_envs
from typing import List

DEFAULT_RESOURCE_REMOVE_COMPLETE_TIMEOUT = 300
DEFAULT_TIMEOUT = 60

# This stops ssl warnings for unsecure certs
urllib3.disable_warnings()

envs = get_envs()
IP = os.environ.get("KM_IP") or envs.get("host", "")
PORT = os.environ.get("RANCHER_PORT") or envs.get("port", "443")
SERVER_URL = 'https://' + IP + ':' + str(PORT)
# SERVER_URL = 'https://' + IP
BASE_URL = SERVER_URL + '/v3'
AUTH_URL = BASE_URL + '-public/localproviders/local?action=login'
LDAP_AUTH_URL = BASE_URL + '-public/openldapProviders/openldap?action=login'

USER_CLUSTER_ID = envs.get("user_cluster_id", "")
EDGE_CLUSTER_ID = envs.get("edge_cluster_id", "")


class ManagementContext:
    """Contains a client that is scoped to the managment plane APIs. That is,
    APIs that are not specific to a cluster or project."""

    def __init__(self, client, k8s_client=None, user=None):
        self.client = client
        self.k8s_client = k8s_client
        self.user = user


class ClusterContext:
    """Contains a client that is scoped to a specific cluster. Also contains
    a reference to the ManagementContext used to create cluster client and
    the cluster object itself.
    """

    def __init__(self, management, cluster, client):
        self.management = management
        self.cluster = cluster
        self.client = client


class ProjectContext:
    """Contains a client that is scoped to a newly created project. Also
    contains a reference to the clusterContext used to crete the project and
    the project object itself.
    """

    def __init__(self, cluster_context, project, namespace, client):
        self.cluster_mc = cluster_context
        self.project = project
        self.namespace = namespace
        self.client = client
		
def protect_response(r):
    if r.status_code >= 300:
        message = f'Server responded with {r.status_code}\nbody:\n{r.text}'
        raise ValueError(message)


def kubernetes_api_client(rancher_client, cluster_name):
    c = rancher_client.by_id_cluster(cluster_name)
    kc = c.generateKubeconfig()
    loader = KubeConfigLoader(config_dict=yaml.full_load(kc.config))
    client_configuration = type.__call__(Configuration)
    loader.load_and_set(client_configuration)
    k8s_client = ApiClient(configuration=client_configuration)
    return k8s_client


def cluster_and_client(cluster_id, mgmt_client):
    cluster = mgmt_client.by_id_cluster(cluster_id)
    url = cluster.links.self
    client = rancher.Client(url=url,
                            verify=False,
                            token=mgmt_client.token,
                            headers={"Content-Type": "application/json"})
    return cluster, client
	
	
@pytest.fixture(scope="session")
def admin_mc():
    """Returns a ManagementContext for the default global admin user."""
    username = envs.get("username", "admin")
    password = envs.get("password", "Admin@123")
    json = {"username": username, "password": password, "responseType": "json"}
    r = requests.post(AUTH_URL, json=json, verify=False)
    protect_response(r)
    client = rancher.Client(url=BASE_URL,
                            token=r.json()['token'],
                            verify=False,
                            headers={"Content-Type": "application/json"})
    # k8s_client = kubernetes_api_client(client, 'local')
    k8s_client = None
    admin = client.list("user", username='admin').data[0]
    return ManagementContext(client, k8s_client, user=admin)


@pytest.fixture
def user_mc(user_factory):
    """Returns a ManagementContext for a new stander user."""
    return user_factory()

@pytest.fixture
def admin_cc(admin_mc):
    """Returns a ClusterContext for the local cluster for the default global admin user."""
    cluster, client = cluster_and_client('local', admin_mc.client)
    return ClusterContext(admin_mc, cluster, client)
	
@pytest.fixture(scope="session")
def user_cc(admin_mc, tmp_path_factory, worker_id, remove_resource_session, request):
    """Returns a ClusterContext for the user cluster for the default global admin user."""
    if hasattr(request, "param"):
        node_num = request.param[0]["node_num"]
        roles = request.param[1]["roles"]
    else:
        node_num = 1
        roles = [["etcd", "control", "worker"]]

    # 从环境变量中读取cluster id 或者指定 cluster id
    cluster_id = os.environ.get("USER_CLUSTER_ID") or USER_CLUSTER_ID

    def get_cluster():
        if cluster_id:
            cluster = admin_mc.client.by_id_cluster(cluster_id)
        else:
            cluster = create_user_cluster(admin_mc.client, node_num, roles)
        # remove_resource_session(cluster)
        return cluster

    if worker_id == "master":
        # 如果是单线程执行，会执行这里的逻辑
        cluster = get_cluster()
        cluster, client = cluster_and_client(cluster.id, admin_mc.client)
        return ClusterContext(admin_mc, cluster, client)

    # 如果是分布式运行，获取所有子节点共享的临时目录
    root_tmp_dir = tmp_path_factory.getbasetemp().parent
    fn = root_tmp_dir / "user_cluster.json"
    with FileLock(str(fn) + ".lock"):
        if fn.is_file():
            # 从缓存中读取clusterId
            cluster_id = json.loads(fn.read_text())
            cluster = admin_mc.client.by_id_cluster(cluster_id)
        else:
            cluster = get_cluster()
            fn.write_text(json.dumps(cluster.id))

        os.environ['user_cluster_id'] = cluster.id
        cluster, client = cluster_and_client(cluster.id, admin_mc.client)
        return ClusterContext(admin_mc, cluster, client)


@pytest.fixture(scope="session")
def user_edge_cc(admin_mc, tmp_path_factory, worker_id, remove_resource_session, request):
    """Returns a ClusterContext for the edge cluster for the default global admin user."""
    # 判断对象是否含有属性
    if hasattr(request, "param"):
        node_num = request.param[0]["node_num"]
        roles = request.param[1]["roles"]
    else:
        node_num = 1
        roles = [["etcd", "control", "worker"]]

    # 从环境变量中读取cluster id 或者指定 cluster id
    cluster_id = os.environ.get("EDGE_CLUSTER_ID") or EDGE_CLUSTER_ID

    def get_cluster():
        if cluster_id:
            cluster = admin_mc.client.by_id_cluster(cluster_id)
        else:
            cluster = create_edge_cluster(admin_mc.client, node_num, roles)
        # remove_resource_session(cluster)
        return cluster

    if worker_id == "master":
        # 如果是单线程执行，会执行这里的逻辑
        cluster = get_cluster()
        cluster, client = cluster_and_client(cluster.id, admin_mc.client)
        return ClusterContext(admin_mc, cluster, client)

    # 如果是分布式运行，获取所有子节点共享的临时目录
    root_tmp_dir = tmp_path_factory.getbasetemp().parent
    fn = root_tmp_dir / "edge_cluster.json"
    with FileLock(str(fn) + ".lock"):
        if fn.is_file():
            # 从缓存中读取clusterId
            cluster_id = json.loads(fn.read_text())
            cluster = admin_mc.client.by_id_cluster(cluster_id)
        else:
            cluster = get_cluster()
            fn.write_text(json.dumps(cluster.id))

        os.environ['edge_cluster_id'] = cluster.id
        cluster, client = cluster_and_client(cluster.id, admin_mc.client)
        return ClusterContext(admin_mc, cluster, client)


@pytest.fixture
def admin_pc_factory(admin_cc, remove_resource):
    """Returns a ProjectContext for a newly created project in the local
    cluster for the default global admin user. The project will be deleted
    when this fixture is cleaned up."""

    def _admin_pc():
        admin_client = admin_cc.management.client
        project = admin_client.create_project(name=random_str(),
                                              clusterId=admin_cc.cluster.id)
        project = admin_client.wait_success(project)
        assert project.state == 'active'
        remove_resource(project)

        project = admin_client.reload(project)
        namespace = admin_cc.client.create_namespace(name=random_str(),
                                                     projectId=project.id)
        url = project.links.self
        return ProjectContext(
            admin_cc,
            project,
            namespace,
            rancher.Client(url=url, verify=False, token=admin_client.token,
                           headers={"Content-Type": "application/json"}))

    return _admin_pc


@pytest.fixture
def admin_pc(admin_pc_factory):
    return admin_pc_factory()


@pytest.fixture(scope="session")
def user_pc(user_cc, remove_resource_session):
    admin_client = user_cc.management.client
    project = admin_client.create_project(name=random_str(),
                                          clusterId=user_cc.cluster.id)
    remove_resource_session(project)
    project = admin_client.wait_success(project)
    assert project.state == 'active'

    project = admin_client.reload(project)
    namespace = user_cc.client.create_namespace(name=random_str(),
                                                projectId=project.id,
                                                cluster_id=user_cc.cluster.id)
    namespace = user_cc.client.wait_success(namespace)
    assert namespace.state == 'active'

    url = project.links.self
    return ProjectContext(
        user_cc,
        project,
        namespace,
        rancher.Client(url=url, verify=False, token=admin_client.token,
                       headers={"Content-Type": "application/json"}))

@pytest.fixture(scope="session")
def user_edge_pc(user_edge_cc, remove_resource_session):
    admin_client = user_edge_cc.management.client
    project = admin_client.create_project(name=random_str(),
                                          clusterId=user_edge_cc.cluster.id)
    remove_resource_session(project)

    project = admin_client.wait_success(project)
    assert project.state == 'active'
    project = admin_client.reload(project)

    namespace = user_edge_cc.client.create_namespace(name=random_str(),
                                                     projectId=project.id)
    namespace = user_edge_cc.client.wait_success(namespace)
    assert namespace.state == 'active'
    url = project.links.self
    return ProjectContext(
        user_edge_cc,
        project,
        namespace,
        rancher.Client(url=url, verify=False, token=admin_client.token,
                       headers={"Content-Type": "application/json"}))


@pytest.fixture(scope="session")
def user_sc(user_cc, admin_mc):
    admin_client = user_cc.management.client
    project = admin_mc.client.list_project(clusterId=user_cc.cluster.id, name='System').data[0]

    project = admin_client.reload(project)

    namespace = None

    url = project.links.self
    return ProjectContext(
        user_cc,
        project,
        namespace,
        rancher.Client(url=url, verify=False, token=admin_client.token,
                       headers={"Content-Type": "application/json"}))


@pytest.fixture(scope="session")
def user_edge_sc(user_edge_cc, admin_mc):
    admin_client = user_edge_cc.management.client
    project = admin_mc.client.list_project(clusterId=user_edge_cc.cluster.id, name='System').data[0]

    project = admin_client.reload(project)

    namespace = None

    url = project.links.self
    return ProjectContext(
        user_edge_cc,
        project,
        namespace,
        rancher.Client(url=url, verify=False, token=admin_client.token,
                       headers={"Content-Type": "application/json"}))

@pytest.fixture(scope="session")
def user_ai_pc(admin_mc, user_edge_cc):
    admin_client = user_edge_cc.management.client
    project = admin_mc.client.list_project(clusterId=user_edge_cc.cluster.id, name='AI-System').data[0]

    project = admin_client.reload(project)

    namespace = user_edge_cc.client.list_namespace(name="ai-algorithm")

    url = project.links.self
    return ProjectContext(
        user_edge_cc,
        project,
        namespace,
        rancher.Client(url=url, verify=False, token=admin_client.token,
                       headers={"Content-Type": "application/json"}))


@pytest.fixture(scope="session")
def user_default_pc(admin_mc, user_edge_cc):
    admin_client = user_edge_cc.management.client
    project = admin_mc.client.list_project(clusterId=user_edge_cc.cluster.id, name='Default').data[0]

    project = admin_client.reload(project)

    namespace = user_edge_cc.client.list_namespace(name="default")

    url = project.links.self
    return ProjectContext(
        user_edge_cc,
        project,
        namespace,
        rancher.Client(url=url, verify=False, token=admin_client.token,
                       headers={"Content-Type": "application/json"}))

@pytest.fixture
def remove_resource(admin_mc, request):
    """
    function 级别清理资源
    """
    client = admin_mc.client

    def _cleanup(*resources):
        def clean_resource(resource):
            try:
                client.delete(resource)
            except ApiError as e:
                if e.error.status != 404:
                    raise e

        def clean():
            for resource in resources:
                clean_resource(resource)

        request.addfinalizer(clean)

    return _cleanup


@pytest.fixture(scope="session")
def remove_resource_session(admin_mc, request):
    """
    session 级别清理资源
    """
    client = admin_mc.client

    def _cleanup(*resources):
        def clean_resource(resource):
            try:
                client.delete(resource)
            except ApiError as e:
                if e.error.status != 404:
                    raise e

        def clean():
            for resource in resources:
                clean_resource(resource)

        request.addfinalizer(clean)

    return _cleanup


@pytest.fixture(scope="module")
def remove_resource_module(admin_mc, request):
    """
    module 级别清理资源
    """
    client = admin_mc.client

    def _cleanup(*resources):
        def clean_resource(resource):
            try:
                client.delete(resource)
            except ApiError as e:
                if e.error.status != 404:
                    raise e

        def clean():
            for resource in resources:
                clean_resource(resource)

        request.addfinalizer(clean)

    return _cleanup

@pytest.fixture
def wait_remove_resource(admin_mc, request, timeout=120):
    """
    function 级别的资源清理
    """
    client = admin_mc.client

    def _cleanup(*resources):
        def clean_resource(resource):
            try:
                client.delete(resource)
            except ApiError as e:
                if e.error.status != 404:
                    raise e

            # wait_until(lambda: client.reload(resource) is None, timeout)
            wait_until(lambda: client.get(resource) is None, timeout)

        def clean():
            for resource in resources:
                clean_resource(resource)

        request.addfinalizer(clean)

    return _cleanup


@pytest.fixture(scope="session")
def wait_remove_resource_session(admin_mc, request, timeout=120):
    """
    session 级别的等待清理资源
    """
    client = admin_mc.client

    def _cleanup(*resources):
        def clean_resource(resource):
            try:
                client.delete(resource)
            except ApiError as e:
                if e.error.status != 404:
                    raise e

            wait_until(lambda: client.get(resource) is None, timeout)

        def clean():
            for resource in resources:
                clean_resource(resource)

        request.addfinalizer(clean)

    return _cleanup


@pytest.fixture(scope="module")
def wait_remove_resource_module(admin_mc, request, timeout=120):
    """
    module 级别的等待清理资源
    """
    client = admin_mc.client

    def _cleanup(*resources):
        def clean_resource(resource):
            try:
                client.delete(resource)
            except ApiError as e:
                if e.error.status != 404:
                    raise e

            wait_until(lambda: client.get(resource) is None, timeout)

        def clean():
            for resource in resources:
                clean_resource(resource)

        request.addfinalizer(clean)

    return _cleanup

@pytest.fixture
def wait_remove_cluster_with_node(admin_mc, request, timeout=DEFAULT_RESOURCE_REMOVE_COMPLETE_TIMEOUT):
    client = admin_mc.client

    def _cleanup(cluster, *nodes):
        def clean_resource(resource, timeout):
            try:
                client.delete(resource)
            except ApiError as e:
                code = e.error.status
                if code == 409 and "namespace will automatically be purged " \
                        in e.error.message:
                    pass
                elif code != 404:
                    raise e
            wait_until(lambda: client.reload(resource) is None, timeout)

        def clean():
            clean_resource(cluster, timeout)
            for node in nodes:
                wait_until(lambda: client.reload(node) is None, timeout)
            time.sleep(15)

        request.addfinalizer(clean)

    return _cleanup


@pytest.fixture(scope="session")
def wait_remove_cluster_with_node_session(admin_mc, request, timeout=DEFAULT_RESOURCE_REMOVE_COMPLETE_TIMEOUT):
    client = admin_mc.client

    def _cleanup(cluster, *nodes):
        def clean_resource(resource, timeout):
            try:
                client.delete(resource)
            except ApiError as e:
                code = e.error.status
                if code == 409 and "namespace will automatically be purged " \
                        in e.error.message:
                    pass
                elif code != 404:
                    raise e
            wait_until(lambda: client.reload(resource) is None, timeout)

        def clean():
            clean_resource(cluster, timeout)
            for node in nodes:
                wait_until(lambda: client.reload(node) is None, timeout)
            time.sleep(15)

        request.addfinalizer(clean)

    return _cleanup


@pytest.fixture(scope="module")
def wait_remove_cluster_with_node_module(admin_mc, request, timeout=DEFAULT_RESOURCE_REMOVE_COMPLETE_TIMEOUT):
    client = admin_mc.client

    def _cleanup(cluster, *nodes):
        def clean_resource(resource, timeout):
            try:
                client.delete(resource)
            except ApiError as e:
                code = e.error.status
                if code == 409 and "namespace will automatically be purged " \
                        in e.error.message:
                    pass
                elif code != 404:
                    raise e
            wait_until(lambda: client.reload(resource) is None, timeout)

        def clean():
            clean_resource(cluster, timeout)
            for node in nodes:
                wait_until(lambda: client.reload(node) is None, timeout)
            time.sleep(15)

        request.addfinalizer(clean)

    return _cleanup

@pytest.fixture
def user_factory(admin_mc, remove_resource, global_roleId="user"):
    """Returns a factory for creating new users which a ManagementContext for
    a newly created standard user is returned.

    This user and globalRoleBinding will be cleaned up automatically by the
    fixture remove_resource.
    """

    def _create_user(globalRoleId=global_roleId):
        admin = admin_mc.client
        username = user_name()
        password = "Admin@123"
        user = admin.create_user(username=username, password=password, name=username)
        remove_resource(user)
        grb = admin.create_global_role_binding(
            userId=user.id, globalRoleId=globalRoleId)
        remove_resource(grb)
        response = requests.post(AUTH_URL, json={
            'username': username,
            'password': password,
            'responseType': 'json',
        }, verify=False)
        protect_response(response)
        client = rancher.Client(url=BASE_URL, token=response.json()['token'],
                                verify=False,
                                headers={"Content-Type": "application/json"})
        return ManagementContext(client, user=user)

    return _create_user

@pytest.fixture
def get_vm_ips():
    pool = VMPoolDriver()
    ips_list = []

    def _func(num=1, arch=""):
        nonlocal ips_list
        if arch == "":
            arch = os.environ.get("ARCHITECTURE") or ARCH_AMD

        ips_list = pool.occupy_vms(num, arch)
        assert len(ips_list) == num
        return ips_list

    return _func

def pytest_addoption(parser):
    """
    增加自定义参数
    """
    parser.addoption("--totp", action="store", default=False, help="上传测试报告到TP")
    # parser.addoption("--cluster-id", action="store", help="指定测试集群id")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    收集测试结果
    :param terminalreporter:
    :param exitstatus:
    :param config:
    :return:
    """
    """
    total = terminalreporter._numcollected
    passed = len([i for i in terminalreporter.stats.get('passed', []) if i.when != 'teardown'])
    failed = len([i for i in terminalreporter.stats.get('failed', []) if i.when != 'teardown'])
    error = len([i for i in terminalreporter.stats.get('error', []) if i.when != 'teardown'])
    skipped = len([i for i in terminalreporter.stats.get('skipped', []) if i.when != 'teardown'])
    successful = len(terminalreporter.stats.get('passed', [])) / terminalreporter._numcollected * 100
    duration = time.time() - terminalreporter._sessionstarttime
    with open("reports/result.txt", "w") as fp:
        fp.write("测试结果统计\n")
        fp.write("URL=%s" % IP + "\n")
        fp.write("TOTAL=%s" % total + "\n")
        fp.write("PASSED=%s" % passed + "\n")
        fp.write("FAILED=%s" % failed + "\n")
        fp.write("ERROR=%s" % error + "\n")
        fp.write("SKIPPED=%s" % skipped + "\n")
        fp.write("SUCCESSFUL=%.2f%%" % successful + "\n")
        fp.write("TOTAL_TIMES=%.2fs" % duration)
    """

    totp = config.option.totp
    if totp:
        exec_path = os.getcwd()  # 执行测试用例的当前路径
        xml_path = config.option.xmlpath  # 相对根目录的路径
        path = os.path.join(exec_path, xml_path)
        package_name = "xml_report.tar.gz"
        packing_targz(path, package_name)
        tp = TP()
        result = tp.upload_report(package_name)
        task_id = result['task_id']
        start = time.time()
        while True:
            if time.time() - start > 60:
                raise AssertionError("查询上报结果超时")
            query_result = tp.query_report(task_id)
            if query_result["status"] == "SUCCESS":
                print("查询上报结果成功")
                break
            time.sleep(2)


@pytest.fixture(scope="session", autouse=True)
def filter_warnings():
    import warnings
    warnings.filterwarnings("ignore")

# 获取云端虚拟节点
def get_cloud_pods(nums=1):
    ip_data_list = []

    def _func(num=nums):
        nonlocal ip_data_list
        ip_data_list = occupy_cloud_pods(num)
        return ip_data_list

    return _func


# 获取边端虚拟节点
def get_edge_pods(nums=1):
    ip_data_list = []

    def _func(num=nums):
        nonlocal ip_data_list
        ip_data_list = occupy_edge_pods(num)
        return ip_data_list

    return _func


# 创建用户集群
def create_user_cluster(client, node_num: int = 1, roles: List[List[str]] = [["etcd", "control", "worker"]]):
    # 获取节点
    pods = get_cloud_pods(node_num)()
    public_ips = [pod["public_ip"] for pod in pods]

    # 创建集群
    kwargs = get_cluster_kwargs(random_str())
    cluster = clusters.create_cluster(client, **kwargs)

    # 添加节点
    for i in range(node_num):
        kwargs = get_node_kwargs(cluster.id, public_ips[i],
                                 etcd=("etcd" in roles[i]),
                                 control=("control" in roles[i]),
                                 worker=("worker" in roles[i]))
        nodes.create_node(client, **kwargs)

    # 等待节点状态为active
    node_list = client.list_node(clusterId=cluster.id).data
    for i in range(node_num):
        node = node_list[i]
        nodes.wait_for_node_create(client, node.id)

    # 等待集群的状态变为active
    reloaded_cluster = wait_for_cluster_active(client, cluster)
    return reloaded_cluster


# 创建边缘集群
def create_edge_cluster(client, node_num: int = 1, roles: List[List[str]] = [["etcd", "control", "worker"]]):
    # 获取节点
    pods = get_cloud_pods(node_num)()
    public_ips = [pod["public_ip"] for pod in pods]
    private_ips = [pod["private_ip"] for pod in pods]
    ssh_ports = [pod["ssh_port"] for pod in pods]
    api_port = [pod["api_port"] for pod in pods]
    tunnel_port = [pod["tunnel_port"] for pod in pods]

    # 创建集群
    kwargs = get_edge_cluster_kwargs(random_str())
    cluster = clusters.create_cluster(client, **kwargs)

    # 添加节点
    for i in range(node_num):
        kwargs = get_edge_node_kwargs(cluster.id, private_ips[i],
                                      public_ips[i], ssh_ports[i],
                                      api_port[i], tunnel_port[i],
                                      etcd=("etcd" in roles[i]),
                                      control=("control" in roles[i]),
                                      worker=("worker" in roles[i]))
        nodes.create_node(client, **kwargs)

    # 等待节点状态为active
    node_list = client.list_node(clusterId=cluster.id).data
    for i in range(node_num):
        node = node_list[i]
        nodes.wait_for_edge_node_create(client, node.id)

    # 等待集群的状态变为active
    # time.sleep(60)
    reloaded_cluster = wait_for_cluster_active(client, cluster)
    return reloaded_cluster
