# 选择基础镜像
FROM docker.sangfor.com/cicd_2598/devops/caas-base:test-v0.3
# 创建者信息
MAINTAINER PAAS

WORKDIR /autotest

COPY pip.conf /autotest
COPY requirements.txt /autotest

# 安装中文支持包
RUN apt-get update && \
    apt-get -y install language-pack-zh-hans && \
    apt-get -y install gcc g++ cmake make build-essential zlib1g-dev libbz2-dev libsqlite3-dev libssl-dev libxslt1-dev libffi-dev

ADD Python-3.8.12.tgz /root
RUN mkdir /usr/local/python38  \
&& cd /root/Python-3.8.12  \
&& ./configure --prefix=/usr/local/python38  \
&& make  \
&& make install \
&& ln -sf /usr/local/python38/bin/python3 /usr/bin/python38 \
&& cp /usr/local/python38/bin/pip3 /usr/bin \
&& cp /usr/local/python38/bin/pip3.8 /usr/bin \
&& rm -rf /root/Python-3.8.12.tgz

# 配置pip安装python包
RUN mkdir ~/.pip && mv /autotest/pip.conf ~/.pip && \
    /usr/local/python38/bin/python3.8 -m pip install --upgrade pip && \
    pip3.8 install -r /autotest/requirements.txt && \
    rm -rf /autotest/requirements.txt


ENV LANG=zh_CN.UTF-8

ADD jdk-8u151-linux-x64.tar.gz /usr/local/java/

ENV JAVA_HOME=/usr/local/java/jdk1.8.0_151
ENV JRE_HOME=$JAVA_HOME/jre
ENV CLASSPATH=$JAVA_HOME/lib:$JRE_HOME/lib
ENV PATH=$PATH:$JAVA_HOME/bin:$JRE_HOME/bin

ADD allure-commandline-2.13.9.tgz  /usr/local/allure/
ENV PATH=$PATH:/usr/local/allure/allure-2.13.9/bin
