#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/8/11 10:00
# software:Vscode
# brief : Alpha Vantage 财报日历数据源

import csv
import io
import json
import urllib.error
import urllib.parse
import urllib.request

from standard_module.config import (
    ALPHA_VANTAGE_API_KEY,
    ALPHA_VANTAGE_API_URL,
    ALPHA_VANTAGE_HORIZON,
    ALPHA_VANTAGE_TIMEOUT,
)


def fetch_earning_calendar():
    """
    从 Alpha Vantage 下载未来财报日历。

    :return: 财报记录列表
    """
    if not ALPHA_VANTAGE_API_KEY or ALPHA_VANTAGE_API_KEY == "YOUR_API_KEY":
        raise ValueError("请在 standard_module/config.py 中配置 Alpha Vantage API Key")
    query = urllib.parse.urlencode(
        {
            "function": "EARNINGS_CALENDAR",
            "horizon": ALPHA_VANTAGE_HORIZON,
            "apikey": ALPHA_VANTAGE_API_KEY,
        }
    )
    request = urllib.request.Request(
        "%s?%s" % (ALPHA_VANTAGE_API_URL, query),
        headers={"User-Agent": "trader-us-earnings-calendar/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=ALPHA_VANTAGE_TIMEOUT) as response:
            content = response.read().decode("utf-8-sig")
    except urllib.error.URLError as error:
        raise RuntimeError("Alpha Vantage 请求失败：%s" % error) from error
    if content.lstrip().startswith("{"):
        raise RuntimeError("Alpha Vantage 未返回财报 CSV：%s" % json.loads(content))
    rows = list(csv.DictReader(io.StringIO(content)))
    if not rows or "reportDate" not in rows[0]:
        raise RuntimeError("Alpha Vantage 返回数据为空或缺少 reportDate 字段")
    return rows
