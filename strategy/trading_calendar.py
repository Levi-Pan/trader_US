#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/09/05 09:18
# software:Vscode
# brief : 财报事件交易日期计算

from bisect import bisect_left, bisect_right
from dataclasses import replace
from datetime import date
from typing import Sequence

from .config import DEFAULT_CONFIG, StrategyConfig
from .models import EarningsEvent, EarningsSession


def get_on_or_next_trading_day(
    target_date: date,
    trading_days: Sequence[date],
) -> date:
    """
    获取目标日期当天或之后最近的交易日。

    :param target_date: 目标日期
    :param trading_days: 已按升序排列的交易日列表
    :return: 当天或之后最近的交易日
    """
    position = bisect_left(trading_days, target_date)

    if position >= len(trading_days):
        raise ValueError(f"找不到{target_date}之后的交易日")

    return trading_days[position]


def get_next_trading_day(
    target_date: date,
    trading_days: Sequence[date],
) -> date:
    """
    获取目标日期之后的第一个交易日。

    :param target_date: 目标日期
    :param trading_days: 已按升序排列的交易日列表
    :return: 下一个交易日
    """
    position = bisect_right(trading_days, target_date)

    if position >= len(trading_days):
        raise ValueError(f"找不到{target_date}之后的交易日")

    return trading_days[position]


def shift_trading_day(
    target_date: date,
    offset: int,
    trading_days: Sequence[date],
) -> date:
    """
    将指定日期按照交易日移动。

    :param target_date: 起始交易日
    :param offset: 移动天数，负数向前，正数向后
    :param trading_days: 已按升序排列的交易日列表
    :return: 移动后的交易日
    """
    position = bisect_left(trading_days, target_date)

    if (
        position >= len(trading_days)
        or trading_days[position] != target_date
    ):
        raise ValueError(f"{target_date}不是交易日")

    result_position = position + offset

    if not 0 <= result_position < len(trading_days):
        raise ValueError(
            f"{target_date}移动{offset}个交易日后超出日历范围"
        )

    return trading_days[result_position]


def get_reaction_day(
    event: EarningsEvent,
    trading_days: Sequence[date],
) -> date | None:
    """
    计算财报公布后的第一个完整反应交易日。

    :param event: 财报事件
    :param trading_days: 已按升序排列的交易日列表
    :return: 财报反应日，时间未知时返回None
    """
    if event.session == EarningsSession.BMO:
        return get_on_or_next_trading_day(
            event.report_date,
            trading_days,
        )

    if event.session == EarningsSession.AMC:
        return get_next_trading_day(
            event.report_date,
            trading_days,
        )

    return None


def build_event_schedule(
    event: EarningsEvent,
    trading_days: Sequence[date],
    config: StrategyConfig = DEFAULT_CONFIG,
) -> EarningsEvent | None:
    """
    计算财报事件的候选、入场和加仓日期。

    :param event: 原始财报事件
    :param trading_days: 已按升序排列的交易日列表
    :param config: 策略参数
    :return: 补充日期后的财报事件，无法确定时返回None
    """
    reaction_day = get_reaction_day(event, trading_days)

    if reaction_day is None:
        return None

    return replace(
        event,
        reaction_day=reaction_day,
        candidate_day=shift_trading_day(
            reaction_day,
            -config.candidate_lead_days,
            trading_days,
        ),
        entry_deadline=shift_trading_day(
            reaction_day,
            -config.entry_deadline_days,
            trading_days,
        ),
        add_deadline=shift_trading_day(
            reaction_day,
            -config.add_deadline_days,
            trading_days,
        ),
    )
