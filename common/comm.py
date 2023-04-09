#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
from functools import wraps
from common.rancher import RestObject


DEFAULT_TIMEOUT = 60


def _sleep_time():
    sleep = 0.01
    while True:
        yield sleep
        sleep *= 2
        if sleep > 1:
            sleep = 1


def wait_for(callback, timeout=DEFAULT_TIMEOUT, fail_handler=None):
    sleep_time = _sleep_time()
    start = time.time()
    ret = callback()
    while ret is None or ret is False:
        time.sleep(next(sleep_time))
        if time.time() - start > timeout:
            exception_msg = 'Timeout waiting for condition.'
            if fail_handler:
                exception_msg = exception_msg + ' Fail handler message: ' + \
                                fail_handler()
            raise Exception(exception_msg)
        ret = callback()
    return ret


def wait_for_condition(condition_type, status, client, obj, timeout=45):
    start = time.time()
    obj = client.reload(obj)
    sleep = 0.01
    while not find_condition(condition_type, status, obj):
        time.sleep(sleep)
        sleep *= 2
        if sleep > 2:
            sleep = 2
        obj = client.reload(obj)
        delta = time.time() - start
        if delta > timeout:
            msg = 'Expected condition {} to have status {}\n' \
                  'Timeout waiting for [{}:{}] for condition after {} ' \
                  'seconds\n {}'.format(condition_type, status, obj.type, obj.id,
                                        delta, str(obj))
            raise Exception(msg)
    return obj


def find_condition(condition_type, status, obj):
    if not hasattr(obj, "conditions"):
        return False

    if obj.conditions is None:
        return False

    for condition in obj.conditions:
        if condition.type == condition_type and condition.status == status:
            return True
    return False


def find_condition_msg(condition_type, msg, obj):
    if not hasattr(obj, "conditions"):
        return False

    if obj.conditions is None:
        return False

    for condition in obj.conditions:
        print(condition.message)
        if condition.type == condition_type and condition.message.find(msg) >= 0:
            return True
    return False

def retry(func, dest, timeout=60, msg='', *args, **kwargs):
    """
    重试机制
    :param func: 函数
    :param dest: 目标
    :param timeout: 时间
    :param msg: 失败返回信息
    :param args:
    :param kwargs:
    :return: 失败抛出异常，成功返回True
    """
    start = time.time()
    interval = 0.5

    while func(*args, **kwargs) != dest:
        if time.time() - start > timeout:
            raise Exception('Timeout waiting ' + msg)
        time.sleep(interval)
        interval = 2 * interval if interval < 5 else 5

    return True


def retry2(func, dest, timeout=30, msg='', *args, **kwargs):
    """
    :return: 失败返回False，成功返回True
    """
    start = time.time()
    interval = 1
    while func(*args, **kwargs) != dest:
        if time.time() - start > timeout:
            return False
        time.sleep(interval)

    return True


def wait_until(cb, timeout=DEFAULT_TIMEOUT, backoff=True):
    """
    等待直到满足某一条件
    可用于判断资源被删除成功
    resource is None
    """
    start_time = time.time()
    interval = 1
    while time.time() < start_time + timeout and cb() is False:
        # if backoff:
        #     interval *= 2
        time.sleep(interval)
        interval = 2 * interval if interval < 5 else 5
    if time.time() > start_time + timeout and cb() is False:
        raise Exception('timeout waiting')

def rtb_cb(client, rtb):
    """等待角色绑定成功"""
    def cb():
        rt = client.reload(rtb)
        return rt.userPrincipalId is not None
    return cb


def calculate_func_run_time(func):
    """
    计算函数运行时间装饰器
    :param func: 被调用的函数
    :return:
    """
    @wraps(func)
    def call_fun(*args, **kwargs):
        start_time = time.time()
        f = func(*args, **kwargs)
        end_time = time.time()
        print('%s() run time：%.2f s' % (func.__name__, end_time - start_time))
        return f

    return call_fun


def check_resource_in_list(resource_list, resource):
    """
    判断资源列表中是否存在要查找的资源
    :param resource_list: 资源列表
    :param resource: 目标资源
    :return:
    """
    found = False
    for item in resource_list:
        if item.id == resource.id:
            found = True
            break
    return found

def check_data(response, expect):
    """
    返回数据与期望数据对比检查
    :param response: 请求返回数据
    :param expect: 期望值
    :return:
    """
    if isinstance(response, RestObject) or isinstance(response, dict):
        response = dict(response)
        for key, value in expect.items():
            assert key in response, f"返回值校验失败，数据：{response}, 返回值中没有要校验对象: {key}"
            check_data(response[key], value)
    elif isinstance(response, list):
        if len(expect) > len(response):
            raise ValueError(f"返回值列表中不存在期待值:{set(expect)^set(response)}")
        for index, item in enumerate(expect):
            check_data(response[index], item)
    else:
        assert expect == response, f"返回值校验失败：期望值：{expect}, 实际值：{response}"


def wait_for_source_state(client, source_type, source_id, state, timeout=120):
    """
    等待资源的转态改变
    :param client: admin用户
    :param source_type: 资源类型
    :param source_id: 资源的id
    :param state: 期望的状态
    :param timeout: 等待超时时间
    :return: 返回状态更新后的资源
    """
    start = time.time()
    interval = 0.5
    updated = False
    while not updated:
        if time.time() - start > timeout:
            raise Exception('Timeout waiting for state to update')
        reload_source = client.by_id(source_type, source_id)
        if reload_source.state == state:
            return reload_source
        time.sleep(interval)
        interval = 2 * interval if interval < 5 else 5


def wait_for_source_build_success(client, source_type, source_id, build_timeout=300):
    """
    等待资源创建或者更新完成：某些资源创建或者更新后资源状态变化为：active->...->active
    """
    is_status_change = False
    start = time.time()
    # 短暂时间内state是active
    while not is_status_change:
        if time.time() - start > 10:
            raise AssertionError(
                "Timed out waiting for source status change ")
        res = client.by_id(source_type, source_id)
        if res.state != "active":
            is_status_change = True
            continue
        time.sleep(2)
    start = time.time()
    is_build_success = False
    while not is_build_success:
        if time.time() - start > build_timeout:
            raise AssertionError(
                "Timed out waiting for build source")
        res = client.by_id(source_type, source_id)
        if res.state == "active":
            is_build_success = True
            continue
        time.sleep(5)
    assert is_build_success is True

