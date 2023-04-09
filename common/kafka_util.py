import pickle
import json
import time
import logging
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import partial
from kafka import KafkaProducer, KafkaConsumer
from config.settings import BOOTSTRAP_SERVERS

logger = logging.getLogger(__name__)


# 加载pkl数据
def load_pkl_file(path, encoding="latin-1", fix_imports=True):
    with open(path, 'rb') as f:
        data = pickle.load(f, encoding=encoding, fix_imports=fix_imports)
        return data


# 获取告警数据
def get_alarm_data(data, engine_name, data_type):
    return data[engine_name][data_type]


# 往kafka写入告警数据
def write_kafka_logs(data, engineName):
    # 获取topic
    dataTypes = list(data[engineName].keys())
    # topics = list(map(lambda s: "SANGFOR_LOG_" + s, data_type))
    print("开启生产者")
    producer = KafkaProducer(value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                             bootstrap_servers=BOOTSTRAP_SERVERS,
                             retries=5,
                             acks="all")
    t = int(round(time.time() * 1000)) - (100 * 3600 * 1000)
    for dataType in dataTypes:
        topic = "SANGFOR_LOG_" + dataType
        alarmMsg = data[engineName][dataType]
        for msg in alarmMsg:
            t = t + 100
            msg["occurTime"] = t
            print(f"写入数据：topic:{topic}, msg:{msg}")
            producer.send(topic, msg)
            producer.flush()


def get_kafka_logs(topic, timeout):
    print("开启消费者")
    end_time = datetime.now() + timedelta(minutes=5)  # 结束时间
    consumer = KafkaConsumer(topic,
                             bootstrap_servers=BOOTSTRAP_SERVERS,
                             value_deserializer=json.loads,
                             consumer_timeout_ms=timeout,
                             group_id="ueba_test",
                             )

    current_time = datetime.now()  # 当前时间
    for message in consumer:
        if current_time > end_time:
            raise ValueError("Kafka消费结束，没有获取到数据")
        value = message.value
        print(f"获取kafka数据：{value}")
        yield value
    else:
        print(f"({topic})没有数据")
        raise ValueError("没有产生告警数据")


def check_kafka_logs(engineName, topic, timeout):
    print("开始检查输出")
    flag = False
    for message in get_kafka_logs(topic, timeout):
        print(f"message:{message}")
        if message['eventName'] == engineName:
            flag = True
            break
        else:
            continue
    return flag


def listen_kafka(kafka_callback, report_callback):
    """监听Kafka队列是否写入数据"""
    with ThreadPoolExecutor(max_workers=1) as executor:
        # 通过子线程启动kafka消费者
        future = executor.submit(
            kafka_callback
        )
        time.sleep(3)

        # 2.请求上报回调函数
        try:
            report_callback()
        except Exception:
            logger.exception(f"上报数据失败!")
            future.result()
            # future.result(timeout=3)
            raise
        return future


def check_result(data, engineName, topic, timeout):
    input_callback = partial(
        write_kafka_logs, data, engineName
    )

    check_callback = partial(
        check_kafka_logs, engineName, topic, timeout
    )

    kafka_result = listen_kafka(
        check_callback, input_callback
    )
    print(kafka_result)
    return kafka_result