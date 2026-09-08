#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 09:26
# software:Vscode
# brief : 财报策略止损与PEAD退出信号判断

from enum import Enum

from .config import DEFAULT_CONFIG, StrategyConfig
from .models import PositionState, SurpriseResult


class ExitAction(str, Enum):
    """持仓退出动作枚举。"""

    HOLD = "HOLD"
    EXIT_STOP = "EXIT_STOP"
    EXIT_MISS = "EXIT_MISS"
    EXIT_UNKNOWN = "EXIT_UNKNOWN"
    EXIT_TIME = "EXIT_TIME"


def check_stop_signal(close_price: float, stop_price: float) -> bool:
    """
    判断收盘价是否触发ATR止损。

    :param close_price: 当前交易日收盘价
    :param stop_price: 当前有效止损价格
    :return: 触发止损返回True，否则返回False
    """
    if close_price <= 0:
        raise ValueError("收盘价必须大于0")
    if stop_price < 0:
        raise ValueError("止损价格不能小于0")

    return stop_price > 0 and close_price <= stop_price


def check_time_exit(
    holding_days_after_event: int,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> bool:
    """
    判断财报后的持有交易日数是否达到时间退出条件。

    :param holding_days_after_event: 财报反应日后的持有交易日数
    :param config: 策略参数
    :return: 达到最大持有天数返回True，否则返回False
    """
    if holding_days_after_event < 0:
        raise ValueError("财报后持有天数不能小于0")

    return holding_days_after_event >= config.maximum_post_earnings_days


def get_post_earnings_action(
    surprise: SurpriseResult,
    holding_days_after_event: int,
    stop_triggered: bool,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> ExitAction:
    """
    按止损、财报结果和持有时限确定财报后的退出动作。

    判断优先级为止损、不及预期、未知结果、时间退出和继续持有。

    :param surprise: 财报预期差分类
    :param holding_days_after_event: 财报反应日后的持有交易日数
    :param stop_triggered: 是否已经触发ATR止损
    :param config: 策略参数
    :return: 对应的退出或继续持有动作
    """
    if holding_days_after_event < 0:
        raise ValueError("财报后持有天数不能小于0")
    if stop_triggered:
        return ExitAction.EXIT_STOP
    if surprise == SurpriseResult.MISS:
        return ExitAction.EXIT_MISS
    if surprise == SurpriseResult.UNKNOWN:
        return ExitAction.EXIT_UNKNOWN
    if check_time_exit(holding_days_after_event, config):
        return ExitAction.EXIT_TIME

    return ExitAction.HOLD


def get_position_exit_action(
    state: PositionState,
    close_price: float,
    earnings_result_available: bool,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> ExitAction:
    """
    根据持仓状态、收盘价和财报数据状态生成退出动作。

    财报公布前只检查ATR止损；财报结果可用后再执行预期差和
    PEAD时间退出规则。

    :param state: 当前持仓状态
    :param close_price: 当前交易日收盘价
    :param earnings_result_available: 财报结果是否已在决策时点可用
    :param config: 策略参数
    :return: 对应的退出或继续持有动作
    """
    stop_triggered = check_stop_signal(close_price, state.stop_price)
    if stop_triggered:
        return ExitAction.EXIT_STOP
    if not earnings_result_available:
        return ExitAction.HOLD

    return get_post_earnings_action(
        state.surprise,
        state.post_earnings_days,
        False,
        config,
    )
