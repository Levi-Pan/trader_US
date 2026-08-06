#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""交易程序统一配置。"""

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent

# Alpha Vantage
ALPHA_VANTAGE_API_KEY = "VSINSG1B5JJG6H8U"
ALPHA_VANTAGE_API_URL = "https://www.alphavantage.co/query"
ALPHA_VANTAGE_TIMEOUT = 30
ALPHA_VANTAGE_HORIZON = "3month"

# 财报日历；空列表表示获取全部公司
EARNINGS_SYMBOLS = []

# 输出文件保存在项目根目录下的 output 文件夹
EARNINGS_OUTPUT_DIR = PROJECT_DIR / "output"
