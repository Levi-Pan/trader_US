#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""每周获取下一自然周的美股财报日历。"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
LOGGER = logging.getLogger("earnings_calendar")
sys.path.append(str(BASE_DIR))

from standard_module.config import (
    ALPHA_VANTAGE_API_KEY,
    ALPHA_VANTAGE_API_URL,
    ALPHA_VANTAGE_HORIZON,
    ALPHA_VANTAGE_TIMEOUT,
    EARNINGS_OUTPUT_DIR,
    EARNINGS_SYMBOLS,
)


def get_next_week_range(run_date: date) -> tuple[date, date]:
    """计算运行日期之后的下一个自然周。"""
    next_monday = run_date + timedelta(days=7 - run_date.weekday())
    return next_monday, next_monday + timedelta(days=6)


def fetch_earnings_calendar(api_key: str, timeout: int) -> list[dict]:
    """从 Alpha Vantage 下载未来三个月财报日历。"""
    query = urllib.parse.urlencode(
        {
            "function": "EARNINGS_CALENDAR",
            "horizon": ALPHA_VANTAGE_HORIZON,
            "apikey": api_key,
        }
    )
    request = urllib.request.Request(
        f"{ALPHA_VANTAGE_API_URL}?{query}",
        headers={"User-Agent": "trader-us-earnings-calendar/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content = response.read().decode("utf-8-sig")
    except urllib.error.URLError as error:
        raise RuntimeError(f"Alpha Vantage 请求失败：{error}") from error
    if content.lstrip().startswith("{"):
        raise RuntimeError(f"Alpha Vantage 未返回财报 CSV：{json.loads(content)}")
    rows = list(csv.DictReader(io.StringIO(content)))
    if not rows or "reportDate" not in rows[0]:
        raise RuntimeError("Alpha Vantage 返回数据为空或缺少 reportDate 字段")
    return rows


def filter_next_week(
    rows: list[dict], start_date: date, end_date: date, symbols: list[str]
) -> list[dict]:
    """筛选下一周财报，并按可选股票池过滤。"""
    symbol_set = {symbol.strip().upper() for symbol in symbols if symbol.strip()}
    results = []
    for row in rows:
        try:
            report_date = datetime.strptime(row["reportDate"], "%Y-%m-%d").date()
        except (KeyError, TypeError, ValueError):
            LOGGER.warning("跳过无效记录：%s", row)
            continue
        symbol = row.get("symbol", "").upper()
        if start_date <= report_date <= end_date and (
            not symbol_set or symbol in symbol_set
        ):
            result = dict(row)
            result["symbol"] = symbol
            result["session"] = "UNKNOWN"
            result["status"] = "ESTIMATED"
            result["source"] = "Alpha Vantage"
            results.append(result)
    return sorted(results, key=get_earnings_sort_key)


def get_earnings_sort_key(row: dict) -> tuple:
    """按盘前、盘后、未知排序，同一时段内 EPS 预测由高到低。"""
    session_order = {
        "pre-market": 0,
        "post-market": 1,
    }
    try:
        estimate_order = -float(row.get("estimate", ""))
        estimate_missing = 0
    except (TypeError, ValueError):
        estimate_order = 0.0
        estimate_missing = 1
    return (
        session_order.get(row.get("timeOfTheDay", ""), 2),
        estimate_missing,
        estimate_order,
        row.get("reportDate", ""),
        row.get("symbol", ""),
    )


def save_csv(rows: list[dict], output_path: Path) -> None:
    """保存为 UTF-8 BOM CSV，便于 Excel 直接打开。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    default_fields = [
        "symbol", "name", "reportDate", "fiscalDateEnding", "estimate",
        "currency", "session", "status", "source", "timeOfTheDay",
    ]
    extra_fields = sorted({key for row in rows for key in row if key not in default_fields})
    field_mapping = {
        "symbol": "股票代码 / 交易代码",
        "name": "公司名称",
        "reportDate": "报告日期 / 发布日期（财报正式公布日期）",
        "fiscalDateEnding": "财报截止日期（所报告季度的最后一天）",
        "estimate": "每股收益预测（EPS预测）",
        "currency": "货币单位",
        "session": "交易时段（指财报发布的时间段，如盘前、盘后）",
        "status": "状态（如：已确认/预估）",
        "source": "数据来源",
        "timeOfTheDay": "具体发布时间（如：盘前/盘后）",
    }
    source_fields = default_fields + extra_fields
    output_fields = [field_mapping.get(field, field) for field in source_fields]
    with output_path.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(
            {
                field_mapping.get(field, field): row.get(field, "")
                for field in source_fields
            }
            for row in rows
        )


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="获取下一周美股财报日历")
    parser.add_argument("--allow-any-day", action="store_true", help="允许非周一手工运行")
    parser.add_argument("--run-date", help="指定运行日期 YYYY-MM-DD，仅用于补跑或测试")
    return parser.parse_args()


def main() -> int:
    """执行财报日历采集任务。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args()
    if not ALPHA_VANTAGE_API_KEY:
        raise ValueError("请配置环境变量 ALPHAVANTAGE_API_KEY")
    run_date = (
        datetime.strptime(args.run_date, "%Y-%m-%d").date()
        if args.run_date
        else datetime.now().date()
    )
    if run_date.weekday() != 0 and not args.allow_any_day:
        LOGGER.info("当前日期 %s 不是周一，任务退出", run_date)
        return 0
    start_date, end_date = get_next_week_range(run_date)
    LOGGER.info("获取 %s 至 %s 的财报日历", start_date, end_date)
    rows = fetch_earnings_calendar(ALPHA_VANTAGE_API_KEY, ALPHA_VANTAGE_TIMEOUT)
    results = filter_next_week(rows, start_date, end_date, EARNINGS_SYMBOLS)
    output_path = EARNINGS_OUTPUT_DIR / f"earnings_{start_date}_{end_date}.csv"
    save_csv(results, output_path)
    LOGGER.info("已保存 %s 条记录：%s", len(results), output_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        LOGGER.exception("财报日历任务执行失败")
        sys.exit(1)
