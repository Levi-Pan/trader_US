#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 09:26
# software:Vscode
# brief : 财报策略基本面评分与候选池筛选

from datetime import datetime
from math import ceil
from typing import Sequence

import pandas as pd

from .config import DEFAULT_CONFIG, StrategyConfig


POSITIVE_FACTOR_COLUMNS = (
    "roe",
    "revenue_growth",
    "profit_growth",
    "fcf_margin",
)
NEGATIVE_FACTOR_COLUMNS = (
    "debt_ratio",
    "pe",
)


def select_latest_fundamentals(
    data: pd.DataFrame,
    decision_time: datetime,
    symbols: Sequence[str] | None = None,
) -> pd.DataFrame:
    """
    获取决策时点以前各股票最近一期已公布的基本面。

    :param data: 包含symbol和published_at字段的历史基本面数据
    :param decision_time: 策略决策时间
    :param symbols: 可选股票代码范围
    :return: 每只股票在决策时点可用的最近一期基本面
    """
    required_columns = {"symbol", "published_at"}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        raise ValueError(f"基本面数据缺少字段：{sorted(missing_columns)}")

    available = data.loc[data["published_at"] <= decision_time].copy()
    if symbols is not None:
        normalized_symbols = {symbol.strip().upper() for symbol in symbols}
        available = available.loc[available["symbol"].isin(normalized_symbols)]

    if available.empty:
        return available.reset_index(drop=True)

    available = available.sort_values(
        ["symbol", "published_at"],
        kind="stable",
    )
    return available.drop_duplicates(
        subset=["symbol"],
        keep="last",
    ).reset_index(drop=True)


def calculate_fundamental_score(
    data: pd.DataFrame,
    positive_columns: Sequence[str] = POSITIVE_FACTOR_COLUMNS,
    negative_columns: Sequence[str] = NEGATIVE_FACTOR_COLUMNS,
    minimum_valid_factors: int = 4,
) -> pd.DataFrame:
    """
    使用截面分位数计算基本面综合评分。

    :param data: 单一市场同一决策时点的基本面截面
    :param positive_columns: 数值越大评分越高的字段
    :param negative_columns: 数值越小评分越高的字段
    :param minimum_valid_factors: 计算综合分要求的最少有效因子数
    :return: 增加因子分位数、有效因子数和综合评分的数据
    """
    factor_columns = tuple(positive_columns) + tuple(negative_columns)
    missing_columns = set(factor_columns) - set(data.columns)
    if missing_columns:
        raise ValueError(f"基本面数据缺少字段：{sorted(missing_columns)}")
    if not 1 <= minimum_valid_factors <= len(factor_columns):
        raise ValueError("minimum_valid_factors必须处于有效因子数量范围内")

    result = data.copy()
    score_columns = []
    for column in factor_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    if "pe" in result.columns:
        result.loc[result["pe"] <= 0, "pe"] = pd.NA
    for column in positive_columns:
        score_column = f"{column}_score"
        result[score_column] = result[column].rank(
            method="average",
            pct=True,
        )
        score_columns.append(score_column)

    for column in negative_columns:
        score_column = f"{column}_score"
        result[score_column] = (-result[column]).rank(
            method="average",
            pct=True,
        )
        score_columns.append(score_column)

    result["valid_factor_count"] = result[score_columns].notna().sum(axis=1)
    result["fundamental_score"] = (
        result[score_columns].mean(axis=1, skipna=True) * 100
    )
    result.loc[
        result["valid_factor_count"] < minimum_valid_factors,
        "fundamental_score",
    ] = pd.NA
    return result


def select_top_percent(
    data: pd.DataFrame,
    percent: float = DEFAULT_CONFIG.fundamental_top_percent,
    score_column: str = "fundamental_score",
    group_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """
    按综合评分选取每个截面排名最高的一定比例股票。

    :param data: 已完成基本面评分的数据
    :param percent: 入选比例
    :param score_column: 综合评分字段名
    :param group_columns: 可选分组字段，例如market；不传则全表排名
    :return: 按评分降序排列的入选股票
    """
    if not 0 < percent <= 1:
        raise ValueError("percent必须在0到1之间")
    if score_column not in data.columns:
        raise ValueError(f"数据缺少评分字段：{score_column}")

    valid = data.loc[data[score_column].notna()].copy()
    if valid.empty:
        return valid.reset_index(drop=True)

    groups = list(group_columns or [])
    missing_columns = set(groups) - set(valid.columns)
    if missing_columns:
        raise ValueError(f"分组字段不存在：{sorted(missing_columns)}")

    sort_columns = [score_column]
    ascending = [False]
    if "symbol" in valid.columns:
        sort_columns.append("symbol")
        ascending.append(True)

    if not groups:
        count = max(1, ceil(len(valid) * percent))
        return valid.sort_values(
            sort_columns,
            ascending=ascending,
            kind="stable",
        ).head(count).reset_index(drop=True)

    selected_frames = []
    for _, group in valid.groupby(groups, dropna=False, sort=False):
        count = max(1, ceil(len(group) * percent))
        selected_frames.append(
            group.sort_values(
                sort_columns,
                ascending=ascending,
                kind="stable",
            ).head(count)
        )
    return pd.concat(selected_frames, ignore_index=True)


def build_fundamental_candidates(
    data: pd.DataFrame,
    decision_time: datetime,
    symbols: Sequence[str] | None = None,
    config: StrategyConfig = DEFAULT_CONFIG,
    group_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """
    生成决策时点可用的基本面Top候选池。

    :param data: 历史基本面数据
    :param decision_time: 策略决策时间
    :param symbols: 可选股票代码范围
    :param config: 策略参数
    :param group_columns: 可选市场等截面分组字段
    :return: 基本面评分最高的候选股票
    """
    latest = select_latest_fundamentals(data, decision_time, symbols)
    if latest.empty:
        return latest

    scored = calculate_fundamental_score(latest)
    return select_top_percent(
        scored,
        percent=config.fundamental_top_percent,
        group_columns=group_columns,
    )
