import requests
import logging
from urllib.parse import urljoin


logger = logging.getLogger(__name__)


class TP:
    def __init__(self):
        self.base_url = "http://tp.sangfor.org"

    def upload_report(self, file_path, **kwargs):
        """
        上传执行结果到tp
        """
        url = urljoin(self.base_url, "/reportapi/v1/report/")
        params = {
            "token": "e844af90ee4e11ea8fcdfefcfea8cddc",
            "project_id": 85,
            "version_id": 30,
            "plan_id": 105,
            "framework_type": "junitxml",
            "build_name": "KM自动化",
        }
        if kwargs:
            params.update(kwargs)
        files = {'file': open(file_path, 'rb')}
        response = requests.post(url, data=params, files=files)
        print(f"状态码: {response.status_code}")
        result = response.json()
        print(f"上报结果: {result}")
        if result['code'] != 0:
            raise ValueError("上报失败")
        return result

    def query_report(self, task_id):
        """
        查询上报结果
        """
        url = urljoin(self.base_url, "/reportapi/v1/report/task")
        params = {
            "task_id": task_id
        }
        response = requests.get(url, params=params)
        result = response.json()
        print(f"查询上报结果: {result}")
        return result