#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/10 14:35
# software:Vscode
# brief : 标准化 Alpha Vantage 财报基础数据

from datetime import datetime, timedelta
from typing import Any

import pandas as pd


OUTPUT_COLUMNS = [
    "symbol",
    "report_date",
    "published_at",
    "fiscal_date_ending",
    "revenue",
    "net_income",
    "operating_cashflow",
    "capital_expenditures",
    "free_cashflow",
    "total_assets",
    "total_liabilities",
    "shareholder_equity",
    "roe",
    "debt_ratio",
    "revenue_growth",
    "profit_growth",
    "fcf_margin",
    "pe",
    "source",
]


def normalize_alpha_vantage_fundamentals(
    income_data: dict[str, Any],
    balance_data: dict[str, Any],
    cash_flow_data: dict[str, Any],
) -> pd.DataFrame:
    """
    将 Alpha Vantage 三张季度财报合并为策略基本面表。

    :param income_data: Alpha Vantage 利润表原始数据
    :param balance_data: Alpha Vantage 资产负债表原始数据
    :param cash_flow_data: Alpha Vantage 现金流量表原始数据
    :return: 标准化后的基本面数据
    """
    symbol = str(income_data.get("symbol", "")).strip().upper()
    income_frame = _build_income_frame(symbol, income_data)
    balance_frame = _build_balance_frame(symbol, balance_data)
    cash_flow_frame = _build_cash_flow_frame(symbol, cash_flow_data)

    if income_frame.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    result = income_frame.merge(
        balance_frame,
        on=["symbol", "fiscal_date_ending"],
        how="left",
    ).merge(
        cash_flow_frame,
        on=["symbol", "fiscal_date_ending"],
        how="left",
    )

    result = result.sort_values(
        ["symbol", "fiscal_date_ending"],
        kind="stable",
    ).reset_index(drop=True)

    result["free_cashflow"] = (
        result["operating_cashflow"] - result["capital_expenditures"]
    )
    result["roe"] = _safe_divide(result["net_income"], result["shareholder_equity"])
    result["debt_ratio"] = _safe_divide(result["total_liabilities"], result["total_assets"])
    result["revenue_growth"] = result.groupby("symbol")["revenue"].pct_change(4)
    result["profit_growth"] = result.groupby("symbol")["net_income"].pct_change(4)
    result["fcf_margin"] = _safe_divide(result["free_cashflow"], result["revenue"])
    result["pe"] = pd.NA
    result["source"] = "Alpha Vantage"

    return result[OUTPUT_COLUMNS]


def _build_income_frame(symbol: str, income_data: dict[str, Any]) -> pd.DataFrame:
    """
    标准化利润表季度数据。

    :param symbol: 股票代码
    :param income_data: 利润表原始数据
    :return: 利润表标准字段
    """
    rows = []

    for report in income_data.get("quarterlyReports", []):
        fiscal_date = _parse_date(report.get("fiscalDateEnding"))
        if fiscal_date is None:
            continue

        rows.append({
            "symbol": symbol,
            "report_date": _parse_report_date(report, fiscal_date),
            "published_at": _parse_published_time(report, fiscal_date),
            "fiscal_date_ending": fiscal_date,
            "revenue": _to_float(report.get("totalRevenue")),
            "net_income": _to_float(report.get("netIncome")),
        })

    return pd.DataFrame(rows)


def _build_balance_frame(symbol: str, balance_data: dict[str, Any]) -> pd.DataFrame:
    """
    标准化资产负债表季度数据。

    :param symbol: 股票代码
    :param balance_data: 资产负债表原始数据
    :return: 资产负债表标准字段
    """
    rows = []

    for report in balance_data.get("quarterlyReports", []):
        fiscal_date = _parse_date(report.get("fiscalDateEnding"))
        if fiscal_date is None:
            continue

        rows.append({
            "symbol": symbol,
            "fiscal_date_ending": fiscal_date,
            "total_assets": _to_float(report.get("totalAssets")),
            "total_liabilities": _to_float(report.get("totalLiabilities")),
            "shareholder_equity": _to_float(report.get("totalShareholderEquity")),
        })

    return pd.DataFrame(rows)


def _build_cash_flow_frame(symbol: str, cash_flow_data: dict[str, Any]) -> pd.DataFrame:
    """
    标准化现金流量表季度数据。

    :param symbol: 股票代码
    :param cash_flow_data: 现金流量表原始数据
    :return: 现金流量表标准字段
    """
    rows = []

    for report in cash_flow_data.get("quarterlyReports", []):
        fiscal_date = _parse_date(report.get("fiscalDateEnding"))
        if fiscal_date is None:
            continue

        rows.append({
            "symbol": symbol,
            "fiscal_date_ending": fiscal_date,
            "operating_cashflow": _to_float(report.get("operatingCashflow")),
            "capital_expenditures": _to_float(report.get("capitalExpenditures")),
        })

    return pd.DataFrame(rows)


def _parse_report_date(report: dict[str, Any], fiscal_date: pd.Timestamp) -> pd.Timestamp:
    """
    解析财报公布日期。

    :param report: 单期财报记录
    :param fiscal_date: 财报期末日期
    :return: 财报公布日期
    """
    report_date = _parse_date(report.get("reportedDate"))
    if report_date is not None:
        return report_date
    return fiscal_date + timedelta(days=45)


def _parse_published_time(report: dict[str, Any], fiscal_date: pd.Timestamp) -> datetime:
    """
    解析策略可见时间。

    :param report: 单期财报记录
    :param fiscal_date: 财报期末日期
    :return: 策略可见时间
    """
    report_date = _parse_report_date(report, fiscal_date)
    return datetime.combine(report_date.date(), datetime.max.time())


def _parse_date(value: Any) -> pd.Timestamp | None:
    """
    解析日期字段。

    :param value: 原始日期值
    :return: 日期对象
    """
    if value in (None, "", "None"):
        return None

    result = pd.to_datetime(value, errors="coerce")
    if pd.isna(result):
        return None
    return result.normalize()


def _to_float(value: Any):
    """
    转换数值字段。

    :param value: 原始数值
    :return: 浮点数或缺失值
    """
    if value in (None, "", "None"):
        return pd.NA

    try:
        return float(value)
    except (TypeError, ValueError):
        return pd.NA


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """
    安全计算除法。

    :param numerator: 分子序列
    :param denominator: 分母序列
    :return: 除法结果
    """
    denominator = pd.to_numeric(denominator, errors="coerce")
    numerator = pd.to_numeric(numerator, errors="coerce")
    return numerator.div(denominator.where(denominator != 0))