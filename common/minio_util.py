import os
import minio
# from minio.error import MinioException


class Bucket(object):
    def __init__(self):
        minio_conf = {
            # 'endpoint': '10.61.8.41:31900',
            'endpoint': '10.59.14.111:31900',  # master_test
            'access_key': 'minio',
            'secret_key': 'A1!@p#$%',
            'secure': False
        }
        self.minioClient = minio.Minio(**minio_conf)

    def make_bucket(self, bucket_name):
        try:
            self.minioClient.make_bucket(bucket_name)
            print("创建bucket成功")
        except Exception as err:
            print(err)

    def put_object(self, bucket_name, obj_name, file_path):
        try:
            with open(file_path, 'rb') as file_data:
                file_stat = os.stat(file_path)
                print(self.minioClient.put_object(bucket_name, obj_name,  file_data, file_stat.st_size))
                print("上传文件成功")
        except Exception as err:
            print(err)

    def get_bucket_list(self):
        try:
            buckets = self.minioClient.list_buckets()
            for bucket in buckets:
                print(bucket.name)
        except Exception as err:
            print(err)

    def delete_bucket(self, bucket_name):
        try:
            self.minioClient.remove_bucket(bucket_name)
            print("删除桶成功")
        except Exception as err:
            print(err)

    def get_bucket_files(self, bucket_name, prefix=None, recursive=True):
        """
        获取bucket指定文件夹中的对象
        """
        try:
            objects = self.minioClient.list_objects(bucket_name, prefix=prefix, recursive=recursive)
            obj_list = []
            for obj in objects:
                print(obj.object_name)
                obj_list.append(obj.object_name)
            return obj_list
        except Exception as err:
            print(err)

    def delete_object(self, bucket_name, object_name):
        try:
            self.minioClient.remove_object(bucket_name, object_name)
            print("删除对象成功")
            return True
        except Exception as err:
            print(err)

    def get_s3_address(self, bucket_name="aip", prefix=None):
        """
        获取minio指定bucket中的s3地址
        """
        obj_list = self.minioClient.list_objects(bucket_name, prefix=prefix)
        s3_list = []
        for obj in obj_list:
            s3_list.append(obj.object_name.split("/")[1])
        return s3_list