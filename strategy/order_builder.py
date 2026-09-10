#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/09/08 10:34
# software:Vscode
# brief : 将策略选股结果转换为待执行订单

from datetime import date, datetime
from typing import Sequence

from strategy.models import OrderSide, PendingOrder


def build_buy_orders(selected_symbols:Sequence[str],execute_date:date,shares_per_symbol:int = 1,) -> list[PendingOrder]:
    """
    将选出的股票转换为买入订单
    ：param selected_symbols:策略选出的股票代码
    ：param execute_date:计划执行日期
    ：param shares_per_symbol:每只股票测试买入股数
    ：return:待执行订单列表
    """
    if shares_per_symbol <= 0:
        raise ValueError("每只股票的买入股数必须大于0")
    normalized_symbols = []
    seen_symbols = set()

    for symbol in selected_symbols:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            continue
        if normalized_symbol.endswith(".US"):
            normalized_symbol = normalized_symbol[:-3]
        if normalized_symbol in seen_symbols:
            continue

        normalized_symbols.append(normalized_symbol)
        seen_symbols.add(normalized_symbol)

    signal_time = datetime.now()
    pending_orders = []

    for symbol in normalized_symbols:
        pending_orders.append(
            PendingOrder(
                symbol=symbol,
                event_id=(
                    f"PAPER_{execute_date:%Y%m%d}_"
                    f"{symbol}_INITIAL_ENTRY"
                ),
                side=OrderSide.BUY,
                shares=shares_per_symbol,
                signal_time=signal_time,
                execute_date=execute_date,
                reason="INITIAL_ENTRY",
                reference_price=None,
            )
        )
    return pending_orders

