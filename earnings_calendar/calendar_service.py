#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/8/11 10:00
# software:Vscode
# brief : 下一周财报日历业务服务

import csv
from datetime import datetime, timedelta

from data_sources.alpha_vantage import fetch_earning_calendar
from data_sources.yahoo_finance import enrich_sector
from private_module.private_log import get_logger
from standard_module.config import EARNINGS_OUTPUT_DIR, EARNINGS_SYMBOLS


logger = get_logger("calendar_service")


def get_next_week_range(run_date):
    """
    计算运行日期之后的下一个自然周。

    :param run_date: 任务运行日期
    :return: 下周周一和周日
    """
    next_monday = run_date + timedelta(days=7 - run_date.weekday())
    return next_monday, next_monday + timedelta(days=6)


def get_earnings_sort_key(row):
    """
    生成财报排序键，盘前优先、盘后其次，同组 EPS 由高到低。

    :param row: 财报记录
    :return: 排序元组
    """
    session_order = {"pre-market": 0, "post-market": 1}
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


def filter_next_week(rows, start_date, end_date, symbols):
    """
    筛选下一周财报，并按可选股票池过滤。

    :param rows: Alpha Vantage 原始财报记录
    :param start_date: 下周开始日期
    :param end_date: 下周结束日期
    :param symbols: 可选股票池，空列表表示全部
    :return: 下一周财报记录
    """
    symbol_set = {symbol.strip().upper() for symbol in symbols if symbol.strip()}
    results = []
    for row in rows:
        try:
            report_date = datetime.strptime(row["reportDate"], "%Y-%m-%d").date()
        except (KeyError, TypeError, ValueError):
            logger.warning("跳过无效财报记录：%s", row)
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
    return results


def save_csv(rows, output_path):
    """
    保存 UTF-8 BOM CSV，便于 Excel 直接打开。

    :param rows: 已完成补充与排序的财报记录
    :param output_path: CSV 输出绝对路径
    :return: 无
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    default_fields = [
        "symbol", "name", "sector", "reportDate", "fiscalDateEnding", "estimate",
        "currency", "session", "status", "source", "timeOfTheDay",
    ]
    extra_fields = sorted({key for row in rows for key in row if key not in default_fields})
    field_mapping = {
        "symbol": "股票代码 / 交易代码",
        "name": "公司名称",
        "sector": "所属板块",
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


def run_earning_calendar(run_date, allow_any_day=False):
    """
    运行下一周财报日历采集、板块补充和输出流程。

    :param run_date: 任务运行日期
    :param allow_any_day: 是否允许非周一运行
    :return: 进程退出码
    """
    if run_date.weekday() != 0 and not allow_any_day:
        logger.info("当前日期 %s 不是周一，任务退出", run_date)
        return 0
    start_date, end_date = get_next_week_range(run_date)
    logger.info("获取 %s 至 %s 的财报日历", start_date, end_date)
    rows = fetch_earning_calendar()
    rows = filter_next_week(rows, start_date, end_date, EARNINGS_SYMBOLS)
    rows = enrich_sector(rows)
    rows = sorted(rows, key=get_earnings_sort_key)
    output_path = EARNINGS_OUTPUT_DIR / (
        "earnings_%s_%s.csv" % (start_date, end_date)
    )
    save_csv(rows, output_path)
    logger.info("已保存 %s 条记录：%s", len(rows), output_path)
    return 0
