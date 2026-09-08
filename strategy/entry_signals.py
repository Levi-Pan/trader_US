#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 09:26
# software:Vscode
# brief : 财报策略首次建仓与趋势加仓信号判断

from datetime import date
from math import isfinite
from typing import Any, Mapping

import pandas as pd

from .config import DEFAULT_CONFIG, StrategyConfig
from .models import EarningsEvent, PositionStage, PositionState


ENTRY_FEATURE_COLUMNS = {
    "close",
    "ma20",
    "ma60",
    "ma20_slope",
    "volume_ratio",
    "atr_pct",
}


def _has_finite_values(row: Mapping[str, Any], columns: set[str]) -> bool:
    """
    检查信号字段是否全部为有限数值。

    :param row: 单个交易日的指标数据
    :param columns: 需要检查的字段
    :return: 全部字段有效时返回True
    """
    for column in columns:
        value = row.get(column)
        if pd.isna(value):
            return False
        try:
            if not isfinite(float(value)):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _is_finite_value(value: Any) -> bool:
    """
    判断单个值是否为有限数值。

    :param value: 待检查值
    :return: 值可转换为有限浮点数时返回True
    """
    if pd.isna(value):
        return False
    try:
        return isfinite(float(value))
    except (TypeError, ValueError):
        return False


def is_initial_entry_window(event: EarningsEvent, signal_date: date) -> bool:
    """
    判断日期是否处于首次建仓信号窗口。

    :param event: 已补齐候选日和入场截止日的财报事件
    :param signal_date: 收盘信号日期
    :return: 日期处于E-10至E-3时返回True
    """
    if event.candidate_day is None or event.entry_deadline is None:
        return False
    return event.candidate_day <= signal_date <= event.entry_deadline


def is_add_window(event: EarningsEvent, signal_date: date) -> bool:
    """
    判断日期是否仍允许生成加仓信号。

    :param event: 已补齐候选日和加仓截止日的财报事件
    :param signal_date: 收盘信号日期
    :return: 日期不晚于加仓截止日时返回True
    """
    if event.candidate_day is None or event.add_deadline is None:
        return False
    return event.candidate_day <= signal_date <= event.add_deadline


def check_entry_signal(
    row: Mapping[str, Any],
    config: StrategyConfig = DEFAULT_CONFIG,
) -> tuple[bool, dict[str, bool]]:
    """
    判断趋势、成交量和波动率是否同时满足首次建仓条件。

    :param row: 单个交易日的行情及技术指标
    :param config: 策略参数
    :return: 是否通过及各子条件判断结果
    """
    data_ready = _has_finite_values(row, ENTRY_FEATURE_COLUMNS)
    if not data_ready:
        details = {
            "data_ready": False,
            "trend_ok": False,
            "volume_ok": False,
            "volatility_ok": False,
        }
        return False, details

    trend_ok = (
        row["close"] > row["ma20"] > row["ma60"]
        and row["ma20_slope"] > 0
    )
    volume_ok = row["volume_ratio"] >= config.minimum_volume_ratio
    volatility_ok = 0 < row["atr_pct"] <= config.maximum_atr_percent
    details = {
        "data_ready": True,
        "trend_ok": bool(trend_ok),
        "volume_ok": bool(volume_ok),
        "volatility_ok": bool(volatility_ok),
    }
    return all(details.values()), details


def check_add_signal(
    position: PositionState,
    row: Mapping[str, Any],
    signal_date: date,
    add_deadline: date | None = None,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> tuple[bool, dict[str, bool]]:
    """
    判断已有持仓是否满足下一批30%趋势加仓条件。

    :param position: 当前持仓状态
    :param row: 单个交易日的行情及技术指标
    :param signal_date: 收盘信号日期
    :param add_deadline: 财报事件加仓截止日
    :param config: 策略参数
    :return: 是否允许加仓及各子条件判断结果
    """
    required_columns = {"close", "ma20", "ma60", "ma20_slope"}
    data_ready = _has_finite_values(row, required_columns)
    stage_ok = position.stage in {
        PositionStage.FIRST_ENTRY,
        PositionStage.FIRST_ADD,
    }
    deadline_ok = add_deadline is not None and signal_date <= add_deadline
    position_open = 0 < position.shares < position.target_shares
    trigger_ready = (
        position.trigger_high is not None
        and isfinite(float(position.trigger_high))
    )

    trend_ok = False
    breakout_ok = False
    stop_safe = False
    volatility_ok = False
    if data_ready:
        trend_ok = (
            row["close"] > row["ma20"] > row["ma60"]
            and row["ma20_slope"] > 0
        )
        breakout_ok = trigger_ready and row["close"] > position.trigger_high
        stop_safe = row["close"] > position.stop_price
        atr_percent = row.get("atr_pct")
        volatility_ok = (
            _is_finite_value(atr_percent)
            and 0 < float(atr_percent) <= config.maximum_atr_percent
        )

    details = {
        "data_ready": data_ready,
        "stage_ok": stage_ok,
        "deadline_ok": deadline_ok,
        "position_open": position_open,
        "trigger_ready": trigger_ready,
        "trend_ok": bool(trend_ok),
        "breakout_ok": bool(breakout_ok),
        "stop_safe": bool(stop_safe),
        "volatility_ok": bool(volatility_ok),
    }
    return all(details.values()), details
