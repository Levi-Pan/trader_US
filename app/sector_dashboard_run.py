#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os
import sys

import uvicorn


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
sys.path.append(BASE_DIR)

from standard_module.config import (
    DASHBOARD_HOST,
    DASHBOARD_PORT,
)


if __name__ == "__main__":
    uvicorn.run(
        "realtime_dashboard.web_app:app",
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        reload=False,
    )