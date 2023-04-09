#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import time
import inspect
from loguru import logger

stack_t = inspect.stack()
ins = inspect.getframeinfo(stack_t[1][0])
exec_dir = os.path.dirname(os.path.abspath(ins.filename))
report_dir = os.path.join(exec_dir, "reports")
if os.path.exists(report_dir) is False:
    os.mkdir(report_dir)

now_time = time.strftime("%Y_%m_%d_%H_%M_%S")


class LogConfig:
    def __init__(self, level: str = "DEBUG", colorlog: bool = True):
        self.logger = logger
        self._colorlog = colorlog
        self._console_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</> {file} <level>| {level} | {message}</level>"
        self._log_format = "{time: YYYY-MM-DD HH:mm:ss} {file} | {level} | {message}"
        self._level = level
        self.logfile = os.path.join(report_dir, "autotest.log")
        self.set_level(self._colorlog, self._console_format, self._level)

    def set_level(self, colorlog: bool = True, format: str = None, level: str = "DEBUG"):
        if format is None:
            format = self._console_format
        self.logger.remove()
        self.logger.add(sys.stderr, level=level, colorize=colorlog, format=format)
        self.logger.add(self.logfile, level=level, colorize=False, format=self._log_format, encoding="utf-8")


# log level: TRACE < DEBUG < INFO < SUCCESS < WARNING < ERROR
log_cfg = LogConfig(level="TRACE")
logger = logger
