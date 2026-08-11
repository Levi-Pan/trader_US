#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/8/11 10:00
# software:Vscode
# brief : 项目日志配置

import logging
import os
from datetime import datetime

from standard_module.config import PROJECT_DIR


LOG_DIR = os.path.join(str(PROJECT_DIR), "logs")
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
log_configured = False


def configure_log():
    """
    配置控制台和每日文件日志，进程内只初始化一次。

    :return: 无
    """
    global log_configured
    if log_configured:
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(
        LOG_DIR,
        "earning_calendar_%s.log" % datetime.now().strftime("%Y%m%d"),
    )
    formatter = logging.Formatter(LOG_FORMAT)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    log_configured = True


def get_logger(logger_name):
    """
    获取项目标准日志对象。

    :param logger_name: 日志名称
    :return: logging.Logger 日志对象
    """
    configure_log()
    return logging.getLogger(logger_name)
