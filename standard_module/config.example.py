#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 10:50
# software:Vscode
# brief : 交易程序统一配置模板

import os
from pathlib import Path


PROJECT_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
ALPHA_VANTAGE_API_URL = "https://www.alphavantage.co/query"
ALPHA_VANTAGE_TIMEOUT = 30
ALPHA_VANTAGE_HORIZON = "3month"

EARNINGS_OUTPUT_DIR = PROJECT_DIR / "output"
