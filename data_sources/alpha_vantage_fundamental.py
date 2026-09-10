#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/10 10:05
# software:Vscode
# brief : Alpha Vantage 财报基础数据源

import csv
import hashlib
import io
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from standard_module.config import (
    ALPHA_VANTAGE_API_KEY,
    ALPHA_VANTAGE_API_URL,
    ALPHA_VANTAGE_HORIZON,
    ALPHA_VANTAGE_TIMEOUT,
    PROJECT_DIR,
)


logger = logging.getLogger(__name__)


class AlphaVantageFundamentalClient:
    """
    Alpha Vantage 财报基础数据客户端。

    只负责请求 Alpha Vantage 原始接口数据，不负责策略打分和选股。
    """

    def __init__(
        self,
        api_key: str = ALPHA_VANTAGE_API_KEY,
        api_url: str = ALPHA_VANTAGE_API_URL,
        timeout: int = ALPHA_VANTAGE_TIMEOUT,
        cache_dir: Path | None = None,
        cache_ttl_hours: int = 24,
        max_retries: int = 3,
        retry_sleep_seconds: float = 2.0,
    ):
        """
        初始化 Alpha Vantage 财报客户端。

        :param api_key: Alpha Vantage API Key
        :param api_url: Alpha Vantage API 地址
        :param timeout: 请求超时时间
        :param cache_dir: 缓存目录
        :param cache_ttl_hours: 缓存有效小时数
        :param max_retries: 最大重试次数
        :param retry_sleep_seconds: 重试等待秒数
        :return: 无
        """
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout
        self.cache_dir = cache_dir or PROJECT_DIR / "output" / "cache" / "alpha_vantage"
        self.cache_ttl_hours = cache_ttl_hours
        self.max_retries = max_retries
        self.retry_sleep_seconds = retry_sleep_seconds
        self._validate_config()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_income_statement(self, symbol: str) -> dict[str, Any]:
        """
        获取利润表数据。

        :param symbol: 股票代码，例如 AAPL 或 AAPL.US
        :return: Alpha Vantage 原始利润表数据
        """
        return self._request_json("INCOME_STATEMENT", symbol=symbol)

    def get_balance_sheet(self, symbol: str) -> dict[str, Any]:
        """
        获取资产负债表数据。

        :param symbol: 股票代码，例如 AAPL 或 AAPL.US
        :return: Alpha Vantage 原始资产负债表数据
        """
        return self._request_json("BALANCE_SHEET", symbol=symbol)

    def get_cash_flow(self, symbol: str) -> dict[str, Any]:
        """
        获取现金流量表数据。

        :param symbol: 股票代码，例如 AAPL 或 AAPL.US
        :return: Alpha Vantage 原始现金流量表数据
        """
        return self._request_json("CASH_FLOW", symbol=symbol)

    def get_earnings_calendar(
        self,
        symbol: str | None = None,
        horizon: str = ALPHA_VANTAGE_HORIZON,
    ) -> list[dict[str, str]]:
        """
        获取未来财报日历数据。

        :param symbol: 股票代码；为空时获取全市场财报日历
        :param horizon: 查询范围，支持 3month、6month、12month
        :return: 财报日历记录列表
        """
        params = {
            "function": "EARNINGS_CALENDAR",
            "horizon": horizon,
            "apikey": self.api_key,
        }

        if symbol:
            params["symbol"] = self._normalize_symbol(symbol)

        content = self._request_text(params)

        if content.lstrip().startswith("{"):
            self._check_json_error(json.loads(content))
            raise RuntimeError("Alpha Vantage 财报日历未返回 CSV 数据")

        rows = list(csv.DictReader(io.StringIO(content)))

        if not rows:
            logger.warning("Alpha Vantage 财报日历返回空数据：symbol=%s", symbol)

        return rows

    def _validate_config(self):
        """
        检查 Alpha Vantage 配置是否完整。

        :return: 无
        """
        if not self.api_key or self.api_key == "YOUR_API_KEY":
            raise ValueError("请先在 standard_module/config.py 中配置 ALPHA_VANTAGE_API_KEY")
        if not self.api_url:
            raise ValueError("请先配置 ALPHA_VANTAGE_API_URL")

    def _request_json(self, function_name: str, symbol: str) -> dict[str, Any]:
        """
        请求 Alpha Vantage JSON 接口。

        :param function_name: Alpha Vantage 接口函数名
        :param symbol: 股票代码
        :return: JSON 字典
        """
        params = {
            "function": function_name,
            "symbol": self._normalize_symbol(symbol),
            "apikey": self.api_key,
        }
        cache_path = self._build_cache_path(params)
        cached_content = self._read_cache(cache_path)

        if cached_content is not None:
            data = json.loads(cached_content)
            self._check_json_error(data)
            return data

        content = self._request_text_from_api(params)

        try:
            data = json.loads(content)
        except json.JSONDecodeError as error:
            raise RuntimeError("Alpha Vantage 返回内容不是合法 JSON") from error

        self._check_json_error(data)
        self._write_cache(cache_path, content)

        return data

    def _request_text(self, params: dict[str, str]) -> str:
        """
        请求 Alpha Vantage 接口并返回文本。

        :param params: 请求参数
        :return: 接口返回文本
        """
        cache_path = self._build_cache_path(params)
        cached_content = self._read_cache(cache_path)

        if cached_content is not None:
            return cached_content

        content = self._request_text_from_api(params)

        if content.lstrip().startswith("{"):
            data = json.loads(content)
            self._check_json_error(data)

        self._write_cache(cache_path, content)

        return content

    def _request_text_from_api(self, params: dict[str, str]) -> str:
        """
        从 Alpha Vantage 接口请求文本。

        :param params: 请求参数
        :return: 接口返回文本
        """
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            "%s?%s" % (self.api_url, query),
            headers={"User-Agent": "trader-us-alpha-vantage/1.0"},
        )

        for retry_index in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return response.read().decode("utf-8-sig")
            except urllib.error.URLError as error:
                if retry_index >= self.max_retries:
                    raise RuntimeError("Alpha Vantage 请求失败：%s" % error) from error

                logger.warning(
                    "Alpha Vantage 请求失败，准备重试：retry=%s/%s, error=%s",
                    retry_index,
                    self.max_retries,
                    error,
                )
                time.sleep(self.retry_sleep_seconds)

        raise RuntimeError("Alpha Vantage 请求失败，已达到最大重试次数")

    def _check_json_error(self, data: dict[str, Any]):
        """
        检查 Alpha Vantage JSON 错误信息。

        :param data: Alpha Vantage JSON 数据
        :return: 无
        """
        for error_key in ("Error Message", "Note", "Information"):
            if error_key in data:
                raise RuntimeError("Alpha Vantage 返回提示：%s" % data[error_key])

    def _build_cache_path(self, params: dict[str, str]) -> Path:
        """
        构建缓存文件路径。

        :param params: 请求参数
        :return: 缓存文件路径
        """
        safe_params = {
            key: value
            for key, value in params.items()
            if key != "apikey"
        }
        cache_key = json.dumps(
            safe_params,
            ensure_ascii=False,
            sort_keys=True,
        )
        cache_name = hashlib.md5(cache_key.encode("utf-8")).hexdigest()

        return self.cache_dir / f"{cache_name}.txt"

    def _read_cache(self, cache_path: Path) -> str | None:
        """
        读取缓存文本。

        :param cache_path: 缓存路径
        :return: 缓存文本
        """
        if not cache_path.exists():
            return None

        modified_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expire_time = modified_time + timedelta(hours=self.cache_ttl_hours)

        if datetime.now() > expire_time:
            return None

        logger.info("读取 Alpha Vantage 缓存：path=%s", cache_path)

        return cache_path.read_text(encoding="utf-8")

    def _write_cache(self, cache_path: Path, content: str):
        """
        写入缓存文本。

        :param cache_path: 缓存路径
        :param content: 缓存内容
        :return: 无
        """
        cache_path.write_text(content, encoding="utf-8")

    def _normalize_symbol(self, symbol: str) -> str:
        """
        标准化股票代码为 Alpha Vantage 使用的格式。

        :param symbol: 原始股票代码
        :return: 标准化股票代码
        """
        clean_symbol = symbol.strip().upper()

        if clean_symbol.endswith(".US"):
            return clean_symbol[:-3]

        return clean_symbol