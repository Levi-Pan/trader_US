#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""交易程序统一配置模板。复制为 config.py 后填写本地配置。"""

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent

# Alpha Vantage
ALPHA_VANTAGE_API_KEY = "YOUR_API_KEY"
ALPHA_VANTAGE_API_URL = "https://www.alphavantage.co/query"
ALPHA_VANTAGE_TIMEOUT = 30
ALPHA_VANTAGE_HORIZON = "3month"

# 财报日历；空列表表示获取全部公司
EARNINGS_SYMBOLS = []

# 输出文件保存在项目根目录下的 output 文件夹
EARNINGS_OUTPUT_DIR = PROJECT_DIR / "output"

# Yahoo Finance 公司板块缓存
YFINANCE_CACHE_PATH = EARNINGS_OUTPUT_DIR / "company_profiles.sqlite3"
YFINANCE_CACHE_TTL_DAYS = 30
YFINANCE_MAX_WORKERS = 3
YFINANCE_MAX_RETRIES = 2

# Alpaca实时行情
ALPACA_API_KEY = "YOUR_API_KEY"
ALPACA_API_SECRET = "YOUR_API_SECRET"
ALPACA_DATA_FEED = "iex"

# 实时板块ETF
SECTOR_ETFS = {
    "XLC": "通信服务",
    "XLY": "非必需消费",
    "XLP": "必需消费",
    "XLE": "能源",
    "XLF": "金融",
    "XLV": "医疗",
    "XLI": "工业",
    "XLB": "材料",
    "XLRE": "房地产",
    "XLK": "科技",
    "XLU": "公用事业",
}

REALTIME_REFRESH_SECONDS = 5
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8000

# Alpaca 实时行情
ALPACA_API_KEY = "YOUR_API_KEY"
ALPACA_API_SERRET = "YOUR_API_KEY"
ALPACA_DATA_FEED = "iex"

# 实时板块 ETF
SECTOR_ETFS = {
     "XLC": "通信服务",
    "XLY": "非必需消费",
    "XLP": "必需消费",
    "XLE": "能源",
    "XLF": "金融",
    "XLV": "医疗",
    "XLI": "工业",
    "XLB": "材料",
    "XLRE": "房地产",
    "XLK": "科技",
    "XLU": "公用事业",
}

REALTIME_REFRESH_SECONDS = 5
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8000
