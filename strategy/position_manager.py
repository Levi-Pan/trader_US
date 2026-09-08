#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 09:26
# software:Vscode
# brief : 财报策略分批建仓与ATR止损管理

import math
from datetime import date

from .config import DEFAULT_CONFIG, StrategyConfig
from .models import EarningsEvent, PositionStage, PositionState


def calculate_target_shares(
    nav: float,
    entry_price: float,
    atr: float,
    adv20_dollar: float,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> int:
    """
    根据风险、单票权重和流动性限制计算完整目标股数。

    :param nav: 组合当前净值
    :param entry_price: 预计成交价格
    :param atr: 当前ATR数值
    :param adv20_dollar: 最近20个交易日日均成交额
    :param config: 策略参数
    :return: 满足所有限制的目标股数
    """
    if nav <= 0:
        raise ValueError("组合净值必须大于0")
    if entry_price <= 0:
        raise ValueError("预计成交价格必须大于0")
    if atr <= 0:
        raise ValueError("ATR必须大于0")
    if adv20_dollar < 0:
        raise ValueError("日均成交额不能小于0")

    stop_distance = config.stop_atr_multiple * atr
    risk_shares = math.floor(nav * config.risk_fraction / stop_distance)
    weight_shares = math.floor(
        nav * config.maximum_stock_weight / entry_price
    )
    liquidity_shares = math.floor(
        adv20_dollar * config.maximum_adv_fraction / entry_price
    )
    return max(0, min(risk_shares, weight_shares, liquidity_shares))


def get_tranche_shares(
    target_shares: int,
    current_shares: int,
    stage: PositionStage,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> int:
    """
    根据40%、30%、30%规则计算下一批应买入的股数。

    :param target_shares: 完整目标股数
    :param current_shares: 当前已持有股数
    :param stage: 当前建仓阶段
    :param config: 策略参数
    :return: 下一批计划买入股数，无需买入时返回0
    """
    if target_shares < 0 or current_shares < 0:
        raise ValueError("目标股数和当前股数不能小于0")
    if current_shares > target_shares:
        raise ValueError("当前股数不能大于目标股数")

    if stage == PositionStage.EMPTY:
        planned_shares = round(target_shares * config.tranche_fractions[0])
    elif stage == PositionStage.FIRST_ENTRY:
        planned_shares = round(target_shares * config.tranche_fractions[1])
    elif stage == PositionStage.FIRST_ADD:
        planned_shares = target_shares - current_shares
    else:
        return 0

    return max(0, min(planned_shares, target_shares - current_shares))


def calculate_initial_stop(
    entry_price: float,
    atr: float,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> float:
    """
    计算首次建仓的ATR止损价格。

    :param entry_price: 首次建仓成交价格
    :param atr: 首次建仓时的ATR数值
    :param config: 策略参数
    :return: 初始止损价格
    """
    if entry_price <= 0:
        raise ValueError("建仓价格必须大于0")
    if atr <= 0:
        raise ValueError("ATR必须大于0")

    return max(0.0, entry_price - config.stop_atr_multiple * atr)


def calculate_trailing_stop(
    previous_stop: float,
    highest_close: float,
    atr: float,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> float:
    """
    计算只升不降的ATR移动止损价格。

    :param previous_stop: 上一交易日止损价格
    :param highest_close: 建仓后的最高收盘价
    :param atr: 当前ATR数值
    :param config: 策略参数
    :return: 更新后的移动止损价格
    """
    if previous_stop < 0:
        raise ValueError("原止损价格不能小于0")
    if highest_close <= 0:
        raise ValueError("最高收盘价必须大于0")
    if atr <= 0:
        raise ValueError("ATR必须大于0")

    candidate_stop = highest_close - config.stop_atr_multiple * atr
    return max(previous_stop, candidate_stop, 0.0)


def create_position_state(
    event: EarningsEvent,
    target_shares: int,
) -> PositionState:
    """
    为待建仓财报事件创建空仓状态。

    :param event: 已完成交易日期计算的财报事件
    :param target_shares: 完整目标股数
    :return: 初始化后的持仓状态
    """
    if event.reaction_day is None:
        raise ValueError("财报事件缺少reaction_day")
    if target_shares <= 0:
        raise ValueError("目标股数必须大于0")

    return PositionState(
        event_id=event.event_id,
        symbol=event.symbol,
        stage=PositionStage.EMPTY,
        target_shares=target_shares,
        shares=0,
        avg_entry_price=0.0,
        first_entry_date=None,
        last_entry_date=None,
        trigger_high=None,
        initial_atr=0.0,
        highest_close=0.0,
        stop_price=0.0,
        reaction_day=event.reaction_day,
    )


def apply_buy_fill(
    state: PositionState,
    filled_shares: int,
    execution_price: float,
    execution_date: date,
    signal_high: float,
    atr: float,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> PositionState:
    """
    将一笔买入成交更新到持仓状态并推进建仓阶段。

    :param state: 成交前持仓状态
    :param filled_shares: 实际成交股数
    :param execution_price: 实际成交价格
    :param execution_date: 实际成交日期
    :param signal_high: 本次确认信号K线最高价
    :param atr: 成交时ATR数值
    :param config: 策略参数
    :return: 原地更新后的持仓状态
    """
    if state.stage in (PositionStage.FULL, PositionStage.CLOSED):
        raise ValueError("当前持仓阶段不允许继续买入")
    if filled_shares <= 0:
        raise ValueError("成交股数必须大于0")
    if state.shares + filled_shares > state.target_shares:
        raise ValueError("成交后股数不能超过目标股数")
    if execution_price <= 0 or signal_high <= 0 or atr <= 0:
        raise ValueError("成交价格、信号最高价和ATR必须大于0")

    original_shares = state.shares
    state.shares += filled_shares
    state.avg_entry_price = (
        state.avg_entry_price * original_shares
        + execution_price * filled_shares
    ) / state.shares
    state.last_entry_date = execution_date
    state.trigger_high = signal_high
    state.highest_close = max(state.highest_close, execution_price)

    if state.stage == PositionStage.EMPTY:
        state.stage = PositionStage.FIRST_ENTRY
        state.first_entry_date = execution_date
        state.initial_atr = atr
        state.stop_price = calculate_initial_stop(
            execution_price,
            atr,
            config,
        )
    elif state.stage == PositionStage.FIRST_ENTRY:
        state.stage = PositionStage.FIRST_ADD
    else:
        state.stage = PositionStage.FULL

    return state


def update_position_trailing_stop(
    state: PositionState,
    close_price: float,
    atr: float,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> PositionState:
    """
    更新持仓最高收盘价及只升不降的ATR移动止损。

    :param state: 当前持仓状态
    :param close_price: 当前交易日收盘价
    :param atr: 当前ATR数值
    :param config: 策略参数
    :return: 原地更新后的持仓状态
    """
    if state.stage in (PositionStage.EMPTY, PositionStage.CLOSED):
        return state
    if close_price <= 0 or atr <= 0:
        raise ValueError("收盘价和ATR必须大于0")

    state.highest_close = max(state.highest_close, close_price)
    state.stop_price = calculate_trailing_stop(
        state.stop_price,
        state.highest_close,
        atr,
        config,
    )
    return state


def apply_full_exit(state: PositionState) -> PositionState:
    """
    将持仓状态更新为全部平仓。

    :param state: 平仓前持仓状态
    :return: 原地更新后的持仓状态
    """
    state.shares = 0
    state.stage = PositionStage.CLOSED
    return state
