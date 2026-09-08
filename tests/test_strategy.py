#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 09:27
# software:Vscode
# brief : 财报驱动策略离线回测集成测试

from datetime import datetime, time

import pandas as pd

from strategy.config import StrategyConfig
from strategy.engine import BacktestEngine
from strategy.models import EarningsEvent, EarningsSession, OrderSide
from strategy.performance import calculate_performance


def _build_prices(trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    """
    构造趋势向上且候选日放量的离线行情。

    :param trading_days: 测试交易日序列
    :return: 测试行情数据
    """
    rows = []
    for position, trading_day in enumerate(trading_days):
        close_price = 100.0 + position * 2.0
        rows.append(
            {
                "symbol": "AAA",
                "date": trading_day,
                "open": close_price - 0.5,
                "high": close_price + 1.0,
                "low": close_price - 1.0,
                "close": close_price,
                "volume": 3_000 if position == 6 else 1_000,
            }
        )
    return pd.DataFrame(rows)


def _build_fundamentals() -> pd.DataFrame:
    """
    构造满足评分要求的离线基本面。

    :return: 测试基本面数据
    """
    return pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "published_at": datetime(2026, 1, 1),
                "roe": 0.20,
                "revenue_growth": 0.15,
                "profit_growth": 0.12,
                "fcf_margin": 0.10,
                "debt_ratio": 0.20,
                "pe": 15.0,
            }
        ]
    )


def test_engine_enters_next_open_and_exits_on_miss() -> None:
    """
    验证收盘入场信号次日成交及不及预期后开盘清仓。

    :return: 无返回值
    """
    trading_days = pd.bdate_range("2026-01-05", periods=12)
    reaction_day = trading_days[9].date()
    event = EarningsEvent(
        event_id="AAA_2026_Q1",
        symbol="AAA",
        report_date=reaction_day,
        session=EarningsSession.BMO,
        known_at=datetime.combine(trading_days[0].date(), time(8)),
        status="CONFIRMED",
        source="TEST",
        reaction_day=reaction_day,
        candidate_day=trading_days[6].date(),
        entry_deadline=trading_days[7].date(),
        add_deadline=trading_days[8].date(),
    )
    results = pd.DataFrame(
        [
            {
                "event_id": event.event_id,
                "symbol": "AAA",
                "release_at": datetime.combine(reaction_day, time(8)),
                "actual_eps": 0.9,
                "consensus_eps": 1.0,
                "actual_revenue": 90.0,
                "consensus_revenue": 100.0,
            }
        ]
    )
    config = StrategyConfig(
        candidate_lead_days=3,
        entry_deadline_days=2,
        add_deadline_days=1,
        short_ma_period=2,
        long_ma_period=3,
        ma_slope_lookback=1,
        volume_ma_period=2,
        atr_period=2,
        maximum_atr_percent=0.20,
        maximum_adv_fraction=1.0,
        slippage_bps=0.0,
    )
    engine = BacktestEngine(
        prices=_build_prices(trading_days),
        fundamentals=_build_fundamentals(),
        earnings_results=results,
        events=[event],
        initial_cash=100_000.0,
        config=config,
    )

    result = engine.run()

    assert len(result.trades) >= 2
    assert result.trades[0].side == OrderSide.BUY
    assert result.trades[0].execution_time.date() == trading_days[7].date()
    assert result.trades[-1].side == OrderSide.SELL
    assert result.trades[-1].execution_time.date() == reaction_day
    assert result.trades[-1].reason == "EARNINGS_MISS"
    assert not result.open_positions


def test_engine_keeps_equity_identity() -> None:
    """
    验证每日净值等于现金和持仓市值之和。

    :return: 无返回值
    """
    trading_days = pd.bdate_range("2026-01-05", periods=5)
    engine = BacktestEngine(
        prices=_build_prices(trading_days),
        fundamentals=_build_fundamentals(),
        earnings_results=pd.DataFrame(
            columns=[
                "event_id",
                "symbol",
                "release_at",
                "actual_eps",
                "consensus_eps",
                "actual_revenue",
                "consensus_revenue",
            ]
        ),
        events=[],
        initial_cash=50_000.0,
    )

    result = engine.run()

    expected = result.equity_curve["cash"] + result.equity_curve["market_value"]
    pd.testing.assert_series_equal(
        result.equity_curve["equity"],
        expected,
        check_names=False,
    )


def test_engine_respects_total_weight_limit() -> None:
    """
    验证买入成交不会超过组合总仓位上限。

    :return: 无返回值
    """
    trading_days = pd.bdate_range("2026-01-05", periods=12)
    event = EarningsEvent(
        event_id="AAA_2026_Q1_WEIGHT",
        symbol="AAA",
        report_date=trading_days[9].date(),
        session=EarningsSession.BMO,
        known_at=datetime.combine(trading_days[0].date(), time(8)),
        status="CONFIRMED",
        source="TEST",
        reaction_day=trading_days[9].date(),
        candidate_day=trading_days[6].date(),
        entry_deadline=trading_days[7].date(),
        add_deadline=trading_days[8].date(),
    )
    config = StrategyConfig(
        candidate_lead_days=3,
        entry_deadline_days=2,
        add_deadline_days=1,
        short_ma_period=2,
        long_ma_period=3,
        ma_slope_lookback=1,
        volume_ma_period=2,
        atr_period=2,
        maximum_atr_percent=0.20,
        maximum_stock_weight=0.10,
        maximum_total_weight=0.10,
        maximum_adv_fraction=1.0,
        risk_fraction=1.0,
        slippage_bps=0.0,
    )
    engine = BacktestEngine(
        prices=_build_prices(trading_days),
        fundamentals=_build_fundamentals(),
        earnings_results=pd.DataFrame(
            columns=["event_id", "symbol", "release_at"]
        ),
        events=[event],
        initial_cash=100_000.0,
        config=config,
    )

    result = engine.run()

    bought_value = sum(
        trade.shares * trade.execution_price
        for trade in result.trades
        if trade.side == OrderSide.BUY
    )
    assert bought_value <= 10_000.0


def test_performance_metrics_are_consistent() -> None:
    """
    验证绩效统计的总收益和最大回撤计算。

    :return: 无返回值
    """
    equity_curve = pd.DataFrame(
        {"equity": [100.0, 120.0, 90.0, 110.0]}
    )

    metrics = calculate_performance(equity_curve, trade_count=4)

    assert abs(metrics["total_return"] - 0.10) < 1e-12
    assert abs(metrics["maximum_drawdown"] + 0.25) < 1e-12
    assert metrics["trade_count"] == 4
