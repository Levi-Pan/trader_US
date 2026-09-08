#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 09:27
# software:Vscode
# brief : 财报驱动策略日线事件回测引擎

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Iterable

import pandas as pd

from .config import DEFAULT_CONFIG, StrategyConfig
from .data_loader import get_available_earnings_result
from .earnings_surprise import classify_earnings_surprise
from .entry_signals import check_add_signal, check_entry_signal
from .exit_signals import ExitAction, get_position_exit_action
from .fundamental_factors import build_fundamental_candidates
from .models import (
    EarningsEvent,
    EarningsSession,
    OrderSide,
    PendingOrder,
    PositionStage,
    PositionState,
    SurpriseResult,
    TradeRecord,
)
from .position_manager import (
    apply_buy_fill,
    apply_full_exit,
    calculate_target_shares,
    create_position_state,
    get_tranche_shares,
    update_position_trailing_stop,
)
from .technical_indicators import calculate_entry_features
from .trading_calendar import build_event_schedule


@dataclass
class BacktestResult:
    """
    保存一次回测的主要输出。

    :param equity_curve: 每日净值记录
    :param trades: 成交记录
    :param final_cash: 回测结束时现金
    :param open_positions: 回测结束时尚未平仓的持仓
    :return: 回测结果对象
    """

    equity_curve: pd.DataFrame
    trades: list[TradeRecord]
    final_cash: float
    open_positions: dict[str, PositionState]


@dataclass
class _OrderContext:
    """
    保存订单执行时需要的信号信息。

    :param atr: 产生信号时的ATR
    :param signal_high: 产生信号时的最高价
    :return: 订单上下文对象
    """

    atr: float = 0.0
    signal_high: float = 0.0


@dataclass
class BacktestEngine:
    """
    使用日频行情执行财报驱动策略回测。

    输入数据必须是时点数据。财报事件需包含known_at，基本面需包含
    published_at，财报结果需包含release_at。所有收盘信号均在下一交易日
    开盘成交，避免使用未来数据。

    :param prices: 日频OHLCV行情
    :param fundamentals: 历史基本面数据
    :param earnings_results: 财报实际结果和公布前一致预期
    :param events: 财报事件列表或标准化DataFrame
    :param initial_cash: 初始资金
    :param config: 策略参数
    :return: 回测引擎对象
    """

    prices: pd.DataFrame
    fundamentals: pd.DataFrame
    earnings_results: pd.DataFrame
    events: Iterable[EarningsEvent] | pd.DataFrame
    initial_cash: float = 1_000_000.0
    config: StrategyConfig = DEFAULT_CONFIG
    cash: float = field(init=False)
    positions: dict[str, PositionState] = field(init=False, default_factory=dict)
    pending_orders: list[PendingOrder] = field(init=False, default_factory=list)
    trades: list[TradeRecord] = field(init=False, default_factory=list)
    selected_events: set[str] = field(init=False, default_factory=set)
    closed_events: set[str] = field(init=False, default_factory=set)
    equity_records: list[dict] = field(init=False, default_factory=list)
    _order_contexts: dict[int, _OrderContext] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        """
        校验输入并准备交易日、指标和财报事件。

        :return: 无返回值
        """
        if self.initial_cash <= 0:
            raise ValueError("initial_cash必须大于0")

        self.cash = float(self.initial_cash)
        self.prices = self.prices.copy()
        self.prices["date"] = pd.to_datetime(self.prices["date"]).dt.date
        self.prices["symbol"] = self.prices["symbol"].str.upper()
        self.prices = self.prices.sort_values(["symbol", "date"])
        self.trading_days = sorted(self.prices["date"].dropna().unique())
        if not self.trading_days:
            raise ValueError("行情数据中没有交易日")

        self.feature_data = calculate_entry_features(
            self.prices,
            self.config,
        ).reset_index(drop=True)
        self.event_map = {
            event.event_id: event
            for event in self._prepare_events(self.events)
        }

    def _prepare_events(
        self,
        events: Iterable[EarningsEvent] | pd.DataFrame,
    ) -> list[EarningsEvent]:
        """
        将输入事件转换为已计算策略日期的事件列表。

        :param events: 财报事件列表或标准化DataFrame
        :return: 可参与回测的财报事件列表
        """
        if isinstance(events, pd.DataFrame):
            source_events = [
                EarningsEvent(
                    event_id=str(row.event_id),
                    symbol=str(row.symbol).upper(),
                    report_date=pd.Timestamp(row.report_date).date(),
                    session=EarningsSession(str(row.session).upper()),
                    known_at=pd.Timestamp(row.known_at).to_pydatetime(),
                    status=str(row.status),
                    source=str(row.source),
                )
                for row in events.itertuples(index=False)
            ]
        else:
            source_events = list(events)

        scheduled_events = []
        for event in source_events:
            try:
                scheduled_event = (
                    event
                    if event.reaction_day is not None
                    else build_event_schedule(event, self.trading_days, self.config)
                )
            except ValueError:
                scheduled_event = None
            if scheduled_event is not None:
                scheduled_events.append(scheduled_event)

        return scheduled_events

    def run(self) -> BacktestResult:
        """
        按交易日执行完整回测。

        :return: 包含净值、成交和期末持仓的回测结果
        """
        for trading_day in self.trading_days:
            daily_bars = self._get_daily_bars(trading_day)
            self._process_releases_at_open(trading_day, daily_bars)
            self._execute_pending_orders(trading_day, daily_bars)
            self._update_positions_at_close(trading_day, daily_bars)
            self._select_new_candidates(trading_day)
            self._generate_entry_orders(trading_day, daily_bars)
            self._record_equity(trading_day, daily_bars)

        return BacktestResult(
            equity_curve=pd.DataFrame(self.equity_records),
            trades=list(self.trades),
            final_cash=self.cash,
            open_positions=dict(self.positions),
        )

    def _get_daily_bars(self, trading_day: date) -> dict[str, pd.Series]:
        """
        获取指定交易日全部股票的行情行。

        :param trading_day: 交易日
        :return: 股票代码到行情行的映射
        """
        daily_data = self.feature_data[self.feature_data["date"] == trading_day]
        return {
            str(row["symbol"]): row
            for _, row in daily_data.iterrows()
        }

    def _process_releases_at_open(
        self,
        trading_day: date,
        daily_bars: dict[str, pd.Series],
    ) -> None:
        """
        在开盘处理此时已经可用的财报结果。

        :param trading_day: 当前交易日
        :param daily_bars: 当日行情映射
        :return: 无返回值
        """
        decision_time = datetime.combine(trading_day, time(9, 30))
        for event_id, position in list(self.positions.items()):
            result = get_available_earnings_result(
                self.earnings_results,
                event_id,
                decision_time,
            )
            if result is None or position.surprise != SurpriseResult.UNKNOWN:
                continue

            position.surprise = classify_earnings_surprise(
                result.get("actual_eps"),
                result.get("consensus_eps"),
                result.get("actual_revenue"),
                result.get("consensus_revenue"),
            )
            if position.surprise == SurpriseResult.MISS:
                bar = daily_bars.get(position.symbol)
                if bar is not None:
                    self._fill_exit(position, trading_day, float(bar["open"]), "EARNINGS_MISS")

    def _execute_pending_orders(
        self,
        trading_day: date,
        daily_bars: dict[str, pd.Series],
    ) -> None:
        """
        使用当日开盘价执行到期订单。

        :param trading_day: 当前交易日
        :param daily_bars: 当日行情映射
        :return: 无返回值
        """
        remaining_orders = []
        for order in self.pending_orders:
            if order.execute_date != trading_day:
                remaining_orders.append(order)
                continue

            position = self.positions.get(order.event_id)
            bar = daily_bars.get(order.symbol)
            if position is None:
                self._order_contexts.pop(id(order), None)
                continue
            if bar is None:
                next_day = self._next_trading_day(trading_day)
                if next_day is not None:
                    order.execute_date = next_day
                    remaining_orders.append(order)
                else:
                    self._order_contexts.pop(id(order), None)
                continue

            if order.side == OrderSide.SELL:
                self._fill_exit(position, trading_day, float(bar["open"]), order.reason)
                continue

            self._fill_buy(
                order,
                position,
                trading_day,
                float(bar["open"]),
                daily_bars,
            )

        self.pending_orders = remaining_orders

    def _fill_buy(
        self,
        order: PendingOrder,
        position: PositionState,
        trading_day: date,
        open_price: float,
        daily_bars: dict[str, pd.Series],
    ) -> None:
        """
        执行买入并更新现金和持仓。

        :param order: 待执行买单
        :param position: 持仓状态
        :param trading_day: 成交日期
        :param open_price: 开盘成交基准价
        :param daily_bars: 当日行情映射
        :return: 无返回值
        """
        execution_price = open_price * (1 + self.config.slippage_bps / 10_000)
        affordable_shares = int(
            self.cash / (execution_price * (1 + self.config.commission_rate))
        )
        portfolio_value = self._portfolio_value_at_open(daily_bars)
        current_market_value = portfolio_value - self.cash
        remaining_total_value = max(
            0.0,
            portfolio_value * self.config.maximum_total_weight
            - current_market_value,
        )
        total_weight_shares = int(remaining_total_value / execution_price)
        filled_shares = min(
            order.shares,
            affordable_shares,
            total_weight_shares,
        )
        if filled_shares <= 0:
            self._order_contexts.pop(id(order), None)
            if position.stage == PositionStage.EMPTY:
                self.positions.pop(position.event_id, None)
            return

        commission = filled_shares * execution_price * self.config.commission_rate
        self.cash -= filled_shares * execution_price + commission
        context = self._order_contexts.pop(id(order), _OrderContext())
        apply_buy_fill(
            position,
            filled_shares,
            execution_price,
            trading_day,
            context.signal_high,
            context.atr,
            self.config,
        )
        self.trades.append(
            TradeRecord(
                symbol=order.symbol,
                event_id=order.event_id,
                side=OrderSide.BUY,
                shares=filled_shares,
                signal_time=order.signal_time,
                execution_time=datetime.combine(trading_day, time(9, 30)),
                execution_price=execution_price,
                commission=commission,
                slippage=filled_shares * (execution_price - open_price),
                reason=order.reason,
            )
        )

    def _fill_exit(
        self,
        position: PositionState,
        trading_day: date,
        open_price: float,
        reason: str,
    ) -> None:
        """
        按开盘价平掉指定持仓。

        :param position: 待平仓持仓
        :param trading_day: 成交日期
        :param open_price: 开盘成交基准价
        :param reason: 平仓原因
        :return: 无返回值
        """
        if position.shares <= 0:
            return

        execution_price = open_price * (1 - self.config.slippage_bps / 10_000)
        commission = position.shares * execution_price * self.config.commission_rate
        self.cash += position.shares * execution_price - commission
        self.trades.append(
            TradeRecord(
                symbol=position.symbol,
                event_id=position.event_id,
                side=OrderSide.SELL,
                shares=position.shares,
                signal_time=datetime.combine(trading_day, time(9, 30)),
                execution_time=datetime.combine(trading_day, time(9, 30)),
                execution_price=execution_price,
                commission=commission,
                slippage=position.shares * (open_price - execution_price),
                reason=reason,
            )
        )
        apply_full_exit(position)
        self.positions.pop(position.event_id, None)
        self.closed_events.add(position.event_id)
        cancelled_order_ids = {
            id(order)
            for order in self.pending_orders
            if order.event_id == position.event_id
        }
        self.pending_orders = [
            order for order in self.pending_orders
            if order.event_id != position.event_id
        ]
        for order_id in cancelled_order_ids:
            self._order_contexts.pop(order_id, None)

    def _update_positions_at_close(
        self,
        trading_day: date,
        daily_bars: dict[str, pd.Series],
    ) -> None:
        """
        更新止损和财报后持有天数并生成退出订单。

        :param trading_day: 当前交易日
        :param daily_bars: 当日行情映射
        :return: 无返回值
        """
        next_day = self._next_trading_day(trading_day)
        if next_day is None:
            return

        for position in list(self.positions.values()):
            if position.shares <= 0 or self._has_pending_order(position.event_id):
                continue

            bar = daily_bars.get(position.symbol)
            if bar is None:
                continue

            if trading_day > position.reaction_day:
                position.post_earnings_days += 1
            update_position_trailing_stop(
                position,
                float(bar["close"]),
                float(bar["atr14"]),
                self.config,
            )
            action = get_position_exit_action(
                position,
                float(bar["close"]),
                position.surprise != SurpriseResult.UNKNOWN,
                self.config,
            )
            if (
                action == ExitAction.HOLD
                and position.surprise == SurpriseResult.UNKNOWN
                and position.post_earnings_days
                >= self.config.maximum_post_earnings_days
            ):
                action = ExitAction.EXIT_UNKNOWN
            if action != ExitAction.HOLD:
                self._queue_order(
                    position,
                    OrderSide.SELL,
                    position.shares,
                    trading_day,
                    next_day,
                    str(action.value),
                )
                continue

            event = self.event_map[position.event_id]
            passed, _ = check_add_signal(
                position,
                bar,
                trading_day,
                event.add_deadline,
                self.config,
            )
            if passed and position.stage != PositionStage.FULL:
                shares = get_tranche_shares(
                    position.target_shares,
                    position.shares,
                    position.stage,
                    self.config,
                )
                self._queue_order(
                    position,
                    OrderSide.BUY,
                    shares,
                    trading_day,
                    next_day,
                    "ADD_CONFIRMATION",
                    float(bar["atr14"]),
                    float(bar["high"]),
                )

    def _select_new_candidates(self, trading_day: date) -> None:
        """
        对当日进入候选池的事件执行基本面Top筛选。

        :param trading_day: 当前交易日
        :return: 无返回值
        """
        decision_time = datetime.combine(trading_day, time(23, 59, 59))
        events = [
            event for event in self.event_map.values()
            if event.candidate_day == trading_day
            and event.known_at <= decision_time
            and event.event_id not in self.closed_events
        ]
        if not events:
            return

        candidates = build_fundamental_candidates(
            self.fundamentals,
            decision_time,
            [event.symbol for event in events],
            self.config,
        )
        selected_symbols = set(candidates["symbol"]) if not candidates.empty else set()
        self.selected_events.update(
            event.event_id for event in events
            if event.symbol in selected_symbols
        )

    def _generate_entry_orders(
        self,
        trading_day: date,
        daily_bars: dict[str, pd.Series],
    ) -> None:
        """
        为基本面候选事件生成首批40%建仓订单。

        :param trading_day: 当前交易日
        :param daily_bars: 当日行情映射
        :return: 无返回值
        """
        next_day = self._next_trading_day(trading_day)
        if next_day is None:
            return

        for event_id in sorted(self.selected_events):
            event = self.event_map[event_id]
            if (
                event_id in self.positions
                or event_id in self.closed_events
                or not event.candidate_day <= trading_day <= event.entry_deadline
            ):
                continue

            bar = daily_bars.get(event.symbol)
            if bar is None:
                continue

            passed, _ = check_entry_signal(bar, self.config)
            if not passed:
                continue

            adv20_dollar = float(
                bar.get(
                    "adv20_dollar",
                    bar["close"] * bar.get("volume_ma20", 0),
                )
            )
            target_shares = calculate_target_shares(
                self._portfolio_value(daily_bars),
                float(bar["close"]),
                float(bar["atr14"]),
                adv20_dollar,
                self.config,
            )
            if target_shares <= 0:
                continue

            position = create_position_state(event, target_shares)
            self.positions[event_id] = position
            shares = get_tranche_shares(
                target_shares,
                0,
                PositionStage.EMPTY,
                self.config,
            )
            self._queue_order(
                position,
                OrderSide.BUY,
                shares,
                trading_day,
                next_day,
                "INITIAL_ENTRY",
                float(bar["atr14"]),
                float(bar["high"]),
            )

    def _queue_order(
        self,
        position: PositionState,
        side: OrderSide,
        shares: int,
        signal_date: date,
        execute_date: date,
        reason: str,
        atr: float = 0.0,
        signal_high: float = 0.0,
    ) -> None:
        """
        新增下一交易日执行的订单。

        :param position: 订单对应持仓
        :param side: 买卖方向
        :param shares: 订单股数
        :param signal_date: 信号日期
        :param execute_date: 执行日期
        :param reason: 下单原因
        :param atr: 信号日ATR
        :param signal_high: 信号日最高价
        :return: 无返回值
        """
        if shares <= 0:
            return

        order = PendingOrder(
            symbol=position.symbol,
            event_id=position.event_id,
            side=side,
            shares=shares,
            signal_time=datetime.combine(signal_date, time(16)),
            execute_date=execute_date,
            reason=reason,
        )
        self.pending_orders.append(order)
        self._order_contexts[id(order)] = _OrderContext(atr, signal_high)

    def _has_pending_order(self, event_id: str) -> bool:
        """
        判断事件是否已经存在待执行订单。

        :param event_id: 财报事件编号
        :return: 存在待执行订单时返回True
        """
        return any(order.event_id == event_id for order in self.pending_orders)

    def _next_trading_day(self, trading_day: date) -> date | None:
        """
        获取下一个可用交易日。

        :param trading_day: 当前交易日
        :return: 下一个交易日，日历结束时返回None
        """
        position = self.trading_days.index(trading_day) + 1
        return self.trading_days[position] if position < len(self.trading_days) else None

    def _portfolio_value(self, daily_bars: dict[str, pd.Series]) -> float:
        """
        按当日可得收盘价计算组合总价值。

        :param daily_bars: 当日行情映射
        :return: 组合总价值
        """
        market_value = sum(
            position.shares * float(daily_bars[position.symbol]["close"])
            for position in self.positions.values()
            if position.shares > 0 and position.symbol in daily_bars
        )
        return self.cash + market_value

    def _portfolio_value_at_open(
        self,
        daily_bars: dict[str, pd.Series],
    ) -> float:
        """
        按当日开盘价计算组合总价值。

        :param daily_bars: 当日行情映射
        :return: 开盘时组合总价值
        """
        market_value = sum(
            position.shares * float(daily_bars[position.symbol]["open"])
            for position in self.positions.values()
            if position.shares > 0 and position.symbol in daily_bars
        )
        return self.cash + market_value

    def _record_equity(
        self,
        trading_day: date,
        daily_bars: dict[str, pd.Series],
    ) -> None:
        """
        记录每日现金、持仓市值和净值。

        :param trading_day: 当前交易日
        :param daily_bars: 当日行情映射
        :return: 无返回值
        """
        equity = self._portfolio_value(daily_bars)
        self.equity_records.append(
            {
                "date": trading_day,
                "cash": self.cash,
                "market_value": equity - self.cash,
                "equity": equity,
            }
        )
