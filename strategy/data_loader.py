#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/09/05 09:21
# software:Vscode
# brief : 财报策略数据读取及时点过滤

import os
from datetime import datetime

import pandas as pd


EARNINGS_CALENDAR_COLUMNS = {
    "event_id",
    "symbol",
    "report_date",
    "session",
    "known_at",
    "status",
    "source",
}

PRICE_COLUMNS = {
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
}

FUNDAMENTAL_COLUMNS = {
    "symbol",
    "fiscal_period_end",
    "published_at",
    "roe",
    "revenue_growth",
    "profit_growth",
    "fcf_margin",
    "debt_ratio",
    "pe",
}

EARNINGS_RESULT_COLUMNS = {
    "event_id",
    "symbol",
    "release_at",
    "actual_eps",
    "consensus_eps",
    "actual_revenue",
    "consensus_revenue",
}


def validate_absolute_path(lpath: str) -> None:
    """
    检查本地文件路径是否为绝对路径。

    :param lpath: 本地文件路径
    :return: 无返回值
    """
    if not os.path.isabs(lpath):
        raise ValueError(f"必须使用绝对路径：{lpath}")

    if not os.path.isfile(lpath):
        raise FileNotFoundError(f"文件不存在：{lpath}")


def validate_columns(
    data: pd.DataFrame,
    required_columns: set[str],
    data_name: str,
) -> None:
    """
    检查数据是否包含必需字段。

    :param data: 待检查数据
    :param required_columns: 必需字段集合
    :param data_name: 数据名称
    :return: 无返回值
    """
    missing_columns = required_columns - set(data.columns)

    if missing_columns:
        raise ValueError(
            f"{data_name}缺少字段：{sorted(missing_columns)}"
        )


def load_earnings_calendar(lpath: str) -> pd.DataFrame:
    """
    读取标准化财报日历。

    :param lpath: 财报日历绝对路径
    :return: 标准化财报日历
    """
    validate_absolute_path(lpath)

    data = pd.read_csv(
        lpath,
        parse_dates=["report_date", "known_at"],
    )
    validate_columns(
        data,
        EARNINGS_CALENDAR_COLUMNS,
        "财报日历",
    )

    data["symbol"] = data["symbol"].str.strip().str.upper()
    data["session"] = data["session"].str.strip().str.upper()

    return data.sort_values(
        ["report_date", "symbol", "known_at"]
    ).reset_index(drop=True)


def load_price_data(lpath: str) -> pd.DataFrame:
    """
    读取复权日频行情。

    :param lpath: 行情文件绝对路径
    :return: 标准化行情数据
    """
    validate_absolute_path(lpath)

    data = pd.read_csv(
        lpath,
        parse_dates=["date"],
    )
    validate_columns(data, PRICE_COLUMNS, "日频行情")

    data["symbol"] = data["symbol"].str.strip().str.upper()

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    data[numeric_columns] = data[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )

    data = data.dropna(
        subset=["symbol", "date", "open", "high", "low", "close"]
    )

    return data.sort_values(
        ["symbol", "date"]
    ).drop_duplicates(
        ["symbol", "date"],
        keep="last",
    ).reset_index(drop=True)


def load_fundamental_data(lpath: str) -> pd.DataFrame:
    """
    读取历史基本面数据。

    :param lpath: 基本面数据绝对路径
    :return: 标准化基本面数据
    """
    validate_absolute_path(lpath)

    data = pd.read_csv(
        lpath,
        parse_dates=[
            "fiscal_period_end",
            "published_at",
        ],
    )
    validate_columns(
        data,
        FUNDAMENTAL_COLUMNS,
        "基本面数据",
    )

    data["symbol"] = data["symbol"].str.strip().str.upper()

    return data.sort_values(
        ["symbol", "published_at"]
    ).reset_index(drop=True)


def get_point_in_time_fundamentals(
    data: pd.DataFrame,
    symbol: str,
    decision_time: datetime,
) -> pd.Series | None:
    """
    获取决策时点以前已公布的最近一期基本面。

    :param data: 历史基本面数据
    :param symbol: 股票代码
    :param decision_time: 策略决策时间
    :return: 最近一期基本面，不存在时返回None
    """
    available = data[
        (data["symbol"] == symbol.upper())
        & (data["published_at"] <= decision_time)
    ]

    if available.empty:
        return None

    return available.sort_values(
        "published_at"
    ).iloc[-1]


def get_price_history(
    data: pd.DataFrame,
    symbol: str,
    decision_time: datetime,
    lookback: int = 80,
) -> pd.DataFrame:
    """
    获取决策时点以前的历史行情。

    :param data: 全部日频行情
    :param symbol: 股票代码
    :param decision_time: 策略决策时间
    :param lookback: 返回的最大交易日数量
    :return: 指定股票的历史行情
    """
    available = data[
        (data["symbol"] == symbol.upper())
        & (data["date"] <= decision_time)
    ]

    return available.sort_values(
        "date"
    ).tail(lookback).reset_index(drop=True)


def load_earnings_results(lpath: str) -> pd.DataFrame:
    """
    读取财报实际结果及公布前一致预期。

    :param lpath: 财报结果绝对路径
    :return: 标准化财报结果
    """
    validate_absolute_path(lpath)

    data = pd.read_csv(
        lpath,
        parse_dates=["release_at"],
    )
    validate_columns(
        data,
        EARNINGS_RESULT_COLUMNS,
        "财报结果",
    )

    data["symbol"] = data["symbol"].str.strip().str.upper()

    return data.sort_values(
        ["release_at", "symbol"]
    ).reset_index(drop=True)


def get_available_earnings_result(
    data: pd.DataFrame,
    event_id: str,
    decision_time: datetime,
) -> pd.Series | None:
    """
    获取决策时点已经公布的财报结果。

    :param data: 财报结果数据
    :param event_id: 财报事件编号
    :param decision_time: 策略决策时间
    :return: 可用财报结果，不存在时返回None
    """
    available = data[
        (data["event_id"] == event_id)
        & (data["release_at"] <= decision_time)
    ]

    if available.empty:
        return None

    return available.sort_values(
        "release_at"
    ).iloc[-1]
