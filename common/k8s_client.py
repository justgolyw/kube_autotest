#!/usr/bin/env python
# -*- coding: utf-8 -*-
import yaml
from kubernetes import client
from kubernetes.client import Configuration, ApiClient
from kubernetes.config.kube_config import KubeConfigLoader
import requests
import urllib3
from common.rancher import Client

urllib3.disable_warnings()

SERVER_URL = "https://10.113.78.238"
BASE_URL = SERVER_URL + '/v3'
AUTH_URL = BASE_URL + '-public/localproviders/local?action=login'


def admin():
    """Returns a ManagementContext for the default global admin user."""
    json = {"username": "admin", "password": "Admin@123", "responseType": "json"}
    r = requests.post(AUTH_URL, json=json, verify=False)
    client = Client(url=BASE_URL,
                    token=r.json()['token'],
                    verify=False,
                    headers={"Content-Type": "application/json"})
    return client


class K8sClient(object):
    def __init__(self, rancher_client, cluster_id):
        self.rancher_client = rancher_client
        self.cluster_id = cluster_id
        self.k8s_client = self.k8s_client()

    def k8s_client(self):
        c = self.rancher_client.by_id_cluster(self.cluster_id)
        # kc = c.generateKubeconfig()  # action 生成kubeconfig文件
        kc = self.rancher_client.action(c, "generateKubeconfig")
        loader = KubeConfigLoader(config_dict=yaml.full_load(kc.config))
        client_configuration = type.__call__(Configuration)
        loader.load_and_set(client_configuration)
        # k8s_client = ApiClient(configuration=client_configuration)
        k8s_client = client.CoreV1Api(ApiClient(configuration=client_configuration))
        return k8s_client

    def get_namespace(self):
        data_list = []
        for item in self.k8s_client.list_namespace().items:
            data_list.append(item.metadata.name)
        return data_list

    def get_node(self):
        data_list = []
        for item in self.k8s_client.list_node().items:
            data_list.append(item.metadata.name)
        return data_list

    def get_node_info(self, keys=None):
        data_list = []
        for item in self.k8s_client.list_node().items:
            data_list.append(item.status.node_info)
        return data_list

    def get_node_status(self, keys=None):
        data_list = []
        for item in self.k8s_client.list_node().items:
            data_list.append(item.spec.unschedulable)
        return data_list

    def get_pod(self):
        """
        获取所有命名空间下的pod
        kubectl get pod -A
        :return:
        """
        data_list = []
        for item in self.k8s_client.list_pod_for_all_namespaces(watch=False).items:
            data_list.append(item.metadata.name)
        return data_list

    def get_namespace_pod(self, namespace):
        """
        获取指定命名空间下的pod
        :param namespace:
        :return:
        """
        data_list = []
        for item in self.k8s_client.list_namespaced_pod(watch=False, namespace=namespace).items:
            data_list.append(item.metadata.name)
        return data_list

    def get_service(self):
        """
        获取所有命名空间下的service
        kubectl get service -A
        :return:
        """
        data_list = []
        for item in self.k8s_client.list_service_for_all_namespaces(watch=False).items:
            data_list.append(item.metadata.name)
        return data_list

    def get_namespace_service(self, namespace):
        """
        获取指定命名空间下的service
        :return:
        """
        data_list = []
        for item in self.k8s_client.list_namespaced_service(watch=False, namespace=namespace).items:
            data_list.append(item.metadata.name)
        return data_list

    def get_namespace_secret(self, namespace="cattle-global-data"):
        data_list = []
        for item in self.k8s_client.list_namespaced_secret(watch=False, namespace=namespace).items:
            data_list.append(item.metadata.name)
        return data_list