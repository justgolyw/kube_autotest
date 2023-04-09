import logging
import jenkins
import argparse

logger = logging.getLogger(__name__)


class JenkinsBuild(object):
    def __init__(self, genre):
        self.genre = genre
        try:
            self.server = self.connect_jenkins()
        except Exception:
            logger.error("ERROR", exc_info=True)

    def connect_jenkins(self):
        server = jenkins.Jenkins(
            'http://10.59.14.119:8080/jenkins',
            username='admin',
            password='sangfor123'
        )
        return server

    def get_pattern_jobs(self):
        """
        匹配job
        :return:
        """
        job_name_list = []
        if self.server._get_view_jobs(self.genre) != []:
            jobs = self.server.get_all_jobs()
            if self.genre == "master":
                for job in jobs:
                    if job['name'].startswith('master'):
                        job_name_list.append(job['name'])
            elif self.genre == "release":
                for job in jobs:
                    if job['name'].startswith('release'):
                        job_name_list.append(job['name'])
        return job_name_list

    def build_jobs(self, jobs, **kwargs):
        """
        构建job
        :param jobs:
        :param kwargs:
        :return:
        """
        next_num = {}
        for job_name in jobs:
            job_info = self.server.get_job_info(job_name)
            next_num[job_name] = job_info['nextBuildNumber']
            if kwargs:  # 如果参数是传进来的就用传参，否则就用默认值
                param_dict = kwargs
            else:
                param_dict = {}
                for params in job_info["property"]:
                    print(params)
                    if "parameterDefinitions" in params:
                        for param in params["parameterDefinitions"]:
                            name = param["defaultParameterValue"]["name"]
                            value = param["defaultParameterValue"]["value"]
                            param_dict[name] = value
            if param_dict:
                self.server.build_job(job_name, parameters=param_dict)
            else:
                self.server.build_job(job_name)
        return next_num

    def get_build_result(self, next_num, jobs):
        """
        获取构建结果
        :param next_num:
        :param jobs:
        :return:
        """
        build_info = {}
        for job_name in jobs:
            try:
                build_result = self.server.get_build_info(
                    job_name, next_num[job_name]
                )
                result = build_result['result']
            except jenkins.JenkinsException:
                logger.info("%s is in the queue", job_name)
                result = None
            build_info[job_name] = result

        return build_info


def main(genre):
    server = JenkinsBuild(genre)
    jobs = server.get_pattern_jobs()
    # print(jobs)
    server.build_jobs(jobs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--genre', help='Use case type',
        choices=['master', 'release'],
        default="master"
    )
    genre = parser.parse_args().genre
    main("master")
