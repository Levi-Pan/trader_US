#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/8/11 10:00
# software:Vscode
# brief : Yahoo Finance 公司板块数据源

import random
import sqlite3
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

warnings.filterwarnings(
    "ignore",
    message="Python 3.8 is no longer supported.*",
)
try:
    from cryptography.utils import CryptographyDeprecationWarning

    warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
except ImportError:
    pass

import yfinance as yf

from private_module.private_log import get_logger
from standard_module.config import (
    YFINANCE_CACHE_PATH,
    YFINANCE_CACHE_TTL_DAYS,
    YFINANCE_MAX_RETRIES,
    YFINANCE_MAX_WORKERS,
)


logger = get_logger("yahoo_finance")
rate_limit_event = threading.Event()


def init_cache():
    """
    初始化公司信息 SQLite 缓存表。

    :return: 无
    """
    YFINANCE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(YFINANCE_CACHE_PATH)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS company_profile (
                symbol TEXT PRIMARY KEY,
                sector TEXT NOT NULL,
                industry TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
            """
        )


def load_cached_profiles(symbols):
    """
    读取未过期的公司板块缓存。

    :param symbols: 股票代码集合
    :return: 有效缓存字典
    """
    if not symbols:
        return {}
    expire_time = datetime.now() - timedelta(days=YFINANCE_CACHE_TTL_DAYS)
    placeholders = ",".join("?" for _ in symbols)
    query = (
        "SELECT symbol, sector, industry, fetched_at FROM company_profile "
        "WHERE symbol IN (%s)" % placeholders
    )
    with sqlite3.connect(str(YFINANCE_CACHE_PATH)) as connection:
        records = connection.execute(query, tuple(symbols)).fetchall()
    return {
        symbol: {"sector": sector, "industry": industry}
        for symbol, sector, industry, fetched_at in records
        if datetime.fromisoformat(fetched_at) >= expire_time
    }


def fetch_company_profile(symbol):
    """
    查询单只股票的板块与行业信息。

    :param symbol: Alpha Vantage 股票代码
    :return: 股票代码及板块信息
    """
    if rate_limit_event.is_set():
        return symbol, None
    yahoo_symbol = symbol.replace(".", "-")
    for retry_index in range(YFINANCE_MAX_RETRIES + 1):
        try:
            info = yf.Ticker(yahoo_symbol).get_info()
            return symbol, {
                "sector": info.get("sector") or "UNKNOWN",
                "industry": info.get("industry") or "UNKNOWN",
            }
        except Exception as error:
            error_message = str(error).lower()
            if "too many requests" in error_message or "rate limit" in error_message:
                rate_limit_event.set()
                logger.warning("Yahoo Finance 已触发限流，本轮停止查询剩余股票")
                return symbol, None
            if retry_index >= YFINANCE_MAX_RETRIES:
                logger.warning("股票 %s 板块查询失败：%s", symbol, error)
                return symbol, None
            time.sleep((2 ** retry_index) + random.uniform(0.2, 0.8))
    return symbol, None


def save_profiles(profiles):
    """
    保存公司板块缓存。

    :param profiles: 公司板块信息字典
    :return: 无
    """
    fetched_at = datetime.now().isoformat(timespec="seconds")
    rows = [
        (symbol, profile["sector"], profile["industry"], fetched_at)
        for symbol, profile in profiles.items()
    ]
    with sqlite3.connect(str(YFINANCE_CACHE_PATH)) as connection:
        connection.executemany(
            """
            INSERT INTO company_profile(symbol, sector, industry, fetched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                sector=excluded.sector,
                industry=excluded.industry,
                fetched_at=excluded.fetched_at
            """,
            rows,
        )


def enrich_sector(rows):
    """
    为财报记录补充所属板块，缓存行业信息供后续分析使用。

    :param rows: 下一周财报记录
    :return: 已补充 sector 字段的财报记录
    """
    init_cache()
    rate_limit_event.clear()
    symbols = sorted({row.get("symbol", "") for row in rows if row.get("symbol")})
    profiles = load_cached_profiles(symbols)
    missing_symbols = [symbol for symbol in symbols if symbol not in profiles]
    if missing_symbols:
        logger.info("查询 %s 只股票的 Yahoo Finance 板块信息", len(missing_symbols))
        fetched_profiles = {}
        with ThreadPoolExecutor(max_workers=YFINANCE_MAX_WORKERS) as executor:
            futures = {
                executor.submit(fetch_company_profile, symbol): symbol
                for symbol in missing_symbols
            }
            for future in as_completed(futures):
                symbol, profile = future.result()
                if profile is not None:
                    fetched_profiles[symbol] = profile
        if fetched_profiles:
            save_profiles(fetched_profiles)
        profiles.update(fetched_profiles)
    for row in rows:
        row["sector"] = profiles.get(row.get("symbol", ""), {}).get("sector", "UNKNOWN")
    return rows
