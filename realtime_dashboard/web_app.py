#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse

from private_module.private_log import get_logger
from realtime_dashboard.market_stream import (
    get_sector_snapshot,
    start_market_thread,
)
from standard_module.config import REALTIME_REFRESH_SECONDS


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

HTML_PATH = os.path.join(
    BASE_DIR,
    "web",
    "sector_dashboard.html",
)
logger = get_logger("sector_dashboard")


@asynccontextmanager
async def lifespan(app):
    """
    启动Web服务时启动行情线程。

    :param app: FastAPI对象
    :return: 异步生命周期
    """
    logger.info("启动Alpaca实时行情线程")
    start_market_thread()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def dashboard():
    """
    返回板块看板页面。

    :return: HTML页面
    """
    return FileResponse(HTML_PATH)


@app.get("/api/sectors")
def sectors():
    """
    返回实时板块数据。

    :return: 板块行情JSON
    """
    return {"data": get_sector_snapshot()}


@app.get("/api/config")
def dashboard_config():
    """
    返回看板公开配置。

    :return: 页面刷新秒数
    """
    return {"refresh_seconds": REALTIME_REFRESH_SECONDS}
