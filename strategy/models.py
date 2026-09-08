#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/09/05 08:56
# software:Vscode
# brief : 财报驱动策略公共数据模型
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class EarningsSession(str, Enum):
    """财报发布时段枚举。"""

    BMO = "BMO"  # Before Market Open
    AMC = "AMC"  # After Market Close
    TBD = "TBD"  # To Be Determined


class PositionStage(int, Enum):
    """持仓阶段枚举。"""

    EMPTY = 0  # 尚未建仓
    FIRST_ENTRY = 1  # 已完成40%建仓
    FIRST_ADD = 2  # 已完成40% + 30%建仓
    FULL = 3  # 已完成40% + 30% + 30%建仓
    CLOSED = 4  # 已完成平仓


class SurpriseResult(str, Enum):
    """财报意外结果枚举。"""

    BEAT = "BEAT"  # 超预期
    MISS = "MISS"  # 不及预期
    UNKNOWN = "UNKNOWN"  # 未知


class OrderSide(str, Enum):
    """订单方向枚举。"""

    BUY = "BUY"  # 买入
    SELL = "SELL"  # 卖出


@dataclass(frozen=True)
class EarningsEvent:
    """单次不可变财报事件。"""

    event_id: str
    symbol: str
    report_date: date
    session: EarningsSession
    known_at: datetime
    status: str
    source: str

    # 后续由交易日模块计算
    reaction_day: date | None = None
    candidate_day: date | None = None
    entry_deadline: date | None = None
    add_deadline: date | None = None


@dataclass
class PositionState:
    """单只股票、单次财报事件的持仓状态。"""

    event_id: str
    symbol: str
    stage: PositionStage

    target_shares: int
    shares: int
    avg_entry_price: float

    first_entry_date: date | None
    last_entry_date: date | None

    # 下一次加仓需要突破的价格
    trigger_high: float | None

    # ATR 止损
    initial_atr: float
    highest_close: float
    stop_price: float

    # 财报后状态
    reaction_day: date
    surprise: SurpriseResult = SurpriseResult.UNKNOWN
    post_earnings_days: int = 0


@dataclass
class PendingOrder:
    """收盘产生、下一可交易时点执行的订单。"""

    symbol: str
    event_id: str
    side: OrderSide
    shares: int

    signal_time: datetime
    execute_date: date
    reason: str

    reference_price: float | None = None


@dataclass
class TradeRecord:
    """实际成交记录。"""

    symbol: str
    event_id: str
    side: OrderSide
    shares: int

    signal_time: datetime
    execution_time: datetime
    execution_price: float

    commission: float
    slippage: float
    reason: str
