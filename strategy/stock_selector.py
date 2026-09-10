#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/10 09:34
# software:Vscode
# brief : 根据财报事件、基本面评分和技术指标生成每日候选股票

from datetime import date, datetime, time
import logging
from typing import Sequence

import pandas as pd

from .config import DEFAULT_CONFIG, StrategyConfig
from .entry_signals import check_entry_signal, is_initial_entry_window
from .fundamental_factors import build_fundamental_candidates
from .models import EarningsEvent, EarningsSession
from .technical_indicators import calculate_entry_features
from .trading_calendar import build_event_schedule


logger = logging.getLogger(__name__)


CANDIDATE_COLUMNS = [
    "event_id",
    "symbol",
    "candidate_day",
    "entry_deadline",
    "fundamental_score",
    "close",
    "ma20",
    "ma60",
    "ma20_slope",
    "volume_ratio",
    "atr14",
    "atr_pct",
    "adv20_dollar",
]


def _empty_candidates() -> pd.DataFrame:
    """
    创建空候选结果。

    :return: 空候选股票表
    """
    return pd.DataFrame(columns=CANDIDATE_COLUMNS)


def _convert_events(
    events: pd.DataFrame | Sequence[EarningsEvent],
) -> list[EarningsEvent]:
    """
    将财报事件数据转换为统一模型。

    :param events: 财报事件表或财报事件对象
    :return: 财报事件对象列表
    """
    if not isinstance(events, pd.DataFrame):
        return list(events)

    result = []

    for row in events.itertuples(index=False):
        event = EarningsEvent(
            event_id=str(row.event_id),
            symbol=str(row.symbol).strip().upper(),
            report_date=pd.Timestamp(row.report_date).date(),
            session=EarningsSession(str(row.session).strip().upper()),
            known_at=pd.Timestamp(row.known_at).to_pydatetime(),
            status=str(row.status),
            source=str(row.source),
        )
        result.append(event)

    return result


def _schedule_events(
    events: Sequence[EarningsEvent],
    trading_days: Sequence[date],
    config: StrategyConfig,
) -> list[EarningsEvent]:
    """
    计算财报候选日、入场截止日和财报反应日。

    :param events: 原始财报事件
    :param trading_days: 美股交易日列表
    :param config: 策略配置
    :return: 已补充交易日期的财报事件
    """
    scheduled_events = []

    for event in events:
        try:
            scheduled_event = (
                event
                if event.reaction_day is not None
                else build_event_schedule(
                    event=event,
                    trading_days=trading_days,
                    config=config,
                )
            )
        except ValueError:
            logger.warning(
                "财报事件无法生成交易日计划：event_id=%s, symbol=%s",
                event.event_id,
                event.symbol,
            )
            continue

        if scheduled_event is not None:
            scheduled_events.append(scheduled_event)

    return scheduled_events


def _select_fundamental_events(
    events: Sequence[EarningsEvent],
    fundamentals: pd.DataFrame,
    signal_date: date,
    config: StrategyConfig,
) -> list[tuple[EarningsEvent, float]]:
    """
    按候选日批次进行基本面筛选。

    每个事件只能使用其候选日当时已经公开的基本面数据，
    避免使用未来数据。

    :param events: 已生成日期计划的财报事件
    :param fundamentals: 历史基本面数据
    :param signal_date: 当前收盘信号日期
    :param config: 策略配置
    :return: 通过基本面筛选的事件及评分
    """
    active_events = [
        event
        for event in events
        if is_initial_entry_window(event, signal_date)
    ]

    if not active_events:
        return []

    event_groups: dict[date, list[EarningsEvent]] = {}

    for event in active_events:
        if event.candidate_day is None:
            continue

        event_groups.setdefault(
            event.candidate_day,
            [],
        ).append(event)

    selected_events = []

    for candidate_day, cohort_events in event_groups.items():
        decision_time = datetime.combine(
            candidate_day,
            time(23, 59, 59),
        )

        known_events = [
            event
            for event in cohort_events
            if event.known_at <= decision_time
            and event.status.upper() not in {"CANCELLED", "INVALID"}
        ]

        if not known_events:
            continue

        symbols = sorted({
            event.symbol
            for event in known_events
        })

        candidates = build_fundamental_candidates(
            data=fundamentals,
            decision_time=decision_time,
            symbols=symbols,
            config=config,
        )

        if candidates.empty:
            continue

        score_mapping = candidates.set_index(
            "symbol"
        )["fundamental_score"].to_dict()

        for event in known_events:
            score = score_mapping.get(event.symbol)

            if score is not None:
                selected_events.append(
                    (event, float(score))
                )

    return selected_events


def _get_signal_bars(
    prices: pd.DataFrame,
    signal_date: date,
    config: StrategyConfig,
) -> dict[str, pd.Series]:
    """
    计算技术指标并取得信号日行情。

    :param prices: 历史日线行情
    :param signal_date: 收盘信号日期
    :param config: 策略配置
    :return: 股票代码到信号日行情的映射
    """
    available_prices = prices[
        pd.to_datetime(prices["date"]).dt.date <= signal_date
    ].copy()

    if available_prices.empty:
        return {}

    available_prices["symbol"] = (
        available_prices["symbol"]
        .str.strip()
        .str.upper()
    )

    feature_data = calculate_entry_features(
        data=available_prices,
        config=config,
    )

    feature_data["_trade_date"] = pd.to_datetime(
        feature_data["date"]
    ).dt.date

    signal_data = feature_data[
        feature_data["_trade_date"] == signal_date
    ]

    if signal_data.empty:
        return {}

    signal_data = signal_data.sort_values(
        ["symbol", "date"],
        kind="stable",
    ).drop_duplicates(
        subset=["symbol"],
        keep="last",
    )

    return {
        str(row["symbol"]): row
        for _, row in signal_data.iterrows()
    }


def select_daily_candidates(
    prices: pd.DataFrame,
    fundamentals: pd.DataFrame,
    events: pd.DataFrame | Sequence[EarningsEvent],
    trading_days: Sequence[date],
    signal_date: date,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    生成指定交易日收盘后的候选股票。

    :param prices: 历史日线行情
    :param fundamentals: 历史基本面数据
    :param events: 财报日历事件
    :param trading_days: 美股交易日列表
    :param signal_date: 本次收盘信号日期
    :param config: 策略配置
    :return: 通过基本面和技术面筛选的候选股票
    """
    normalized_events = _convert_events(events)

    scheduled_events = _schedule_events(
        events=normalized_events,
        trading_days=trading_days,
        config=config,
    )

    fundamental_events = _select_fundamental_events(
        events=scheduled_events,
        fundamentals=fundamentals,
        signal_date=signal_date,
        config=config,
    )

    if not fundamental_events:
        logger.info(
            "没有通过基本面筛选的财报事件：signal_date=%s",
            signal_date,
        )
        return _empty_candidates()

    signal_bars = _get_signal_bars(
        prices=prices,
        signal_date=signal_date,
        config=config,
    )

    selected_rows = []

    for event, fundamental_score in fundamental_events:
        bar = signal_bars.get(event.symbol)

        if bar is None:
            logger.warning(
                "缺少信号日行情：symbol=%s, signal_date=%s",
                event.symbol,
                signal_date,
            )
            continue

        passed, signal_details = check_entry_signal(
            row=bar,
            config=config,
        )

        logger.info(
            (
                "技术信号检查：symbol=%s, passed=%s, "
                "trend=%s, volume=%s, volatility=%s"
            ),
            event.symbol,
            passed,
            signal_details["trend_ok"],
            signal_details["volume_ok"],
            signal_details["volatility_ok"],
        )

        if not passed:
            continue

        selected_rows.append({
            "event_id": event.event_id,
            "symbol": event.symbol,
            "candidate_day": event.candidate_day,
            "entry_deadline": event.entry_deadline,
            "fundamental_score": fundamental_score,
            "close": float(bar["close"]),
            "ma20": float(bar["ma20"]),
            "ma60": float(bar["ma60"]),
            "ma20_slope": float(bar["ma20_slope"]),
            "volume_ratio": float(bar["volume_ratio"]),
            "atr14": float(bar["atr14"]),
            "atr_pct": float(bar["atr_pct"]),
            "adv20_dollar": float(bar["adv20_dollar"]),
        })

    if not selected_rows:
        logger.info(
            "没有股票通过技术入场条件：signal_date=%s",
            signal_date,
        )
        return _empty_candidates()

    result = pd.DataFrame(selected_rows)

    result = result.sort_values(
        by=[
            "fundamental_score",
            "volume_ratio",
        ],
        ascending=[
            False,
            False,
        ],
        kind="stable",
    )

    result = result.drop_duplicates(
        subset=["symbol"],
        keep="first",
    ).reset_index(drop=True)

    logger.info(
        "每日选股完成：signal_date=%s, selected=%s",
        signal_date,
        len(result),
    )

    return result[CANDIDATE_COLUMNS]