#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/8/11 10:00
# software:Vscode
# brief : Alpha Vantage 财报日历数据源

import csv
import io
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from standard_module.config import (
    ALPHA_VANTAGE_API_KEY,
    ALPHA_VANTAGE_API_URL,
    ALPHA_VANTAGE_HORIZON,
    ALPHA_VANTAGE_TIMEOUT,
    EARNINGS_OUTPUT_DIR,
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


def save_next_week_calendar():
    """
    下载财报日历并将下一个自然周的原始记录保存为CSV。

    :return: 输出文件绝对路径
    """
    today = datetime.now(timezone(timedelta(hours=8))).date()
    start_date = today + timedelta(days=7 - today.weekday())
    end_date = start_date + timedelta(days=6)
    logging.info("获取%s至%s的财报日历", start_date, end_date)
    rows = fetch_earning_calendar()
    selected = []
    for row in rows:
        try:
            report_date = datetime.strptime(row["reportDate"], "%Y-%m-%d").date()
        except (KeyError, TypeError, ValueError):
            logging.warning("跳过财报日期无效记录：%s", row.get("symbol", ""))
            continue
        if start_date <= report_date <= end_date:
            selected.append(row)
    selected.sort(key=lambda row: (row["reportDate"], row.get("symbol", "")))
    os.makedirs(EARNINGS_OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(str(EARNINGS_OUTPUT_DIR), "earnings_%s_%s.csv" % (start_date, end_date))
    with open(output_path, "w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(selected)
    logging.info("已保存%s条财报记录：%s", len(selected), output_path)
    return output_path
