#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/10 14:55
# software:Vscode
# brief : 测试每日选股数据链路

from datetime import date, timedelta
import logging
import os
import sys

import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from data_sources.alpha_vantage_fundamental import AlphaVantageFundamentalClient
from data_sources.fundamental_dataset import build_alpha_vantage_fundamental_dataset
from data_sources.longbridge_market_dataset import build_longbridge_daily_price_dataset
from strategy.models import EarningsSession
from strategy.stock_selector import select_daily_candidates


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """
    测试每日选股数据链路。

    :return: 无
    """
    symbols = [
        "AAPL",
        "MSFT",
        "NVDA",
    ]

    fundamental_client = AlphaVantageFundamentalClient()

    fundamentals = build_alpha_vantage_fundamental_dataset(
        symbols=symbols,
        client=fundamental_client,
    )

    prices = build_longbridge_daily_price_dataset(
        symbols=symbols,
        count=120,
    )

    if prices.empty:
        logger.warning("长桥行情为空，无法执行每日选股测试")
        return

    signal_date = pd.to_datetime(prices["date"]).dt.date.max()
    trading_days = _build_simple_trading_days(signal_date)

    events = _build_test_events(
        symbols=symbols,
        signal_date=signal_date,
    )

    candidates = select_daily_candidates(
        prices=prices,
        fundamentals=fundamentals,
        events=events,
        trading_days=trading_days,
        signal_date=signal_date,
    )

    logger.info(
        "每日选股测试完成：signal_date=%s, selected=%s",
        signal_date,
        len(candidates),
    )

    if not candidates.empty:
        logger.info(
            "候选股票：%s",
            candidates[
                [
                    "symbol",
                    "fundamental_score",
                    "close",
                    "ma20",
                    "ma60",
                    "volume_ratio",
                    "atr_pct",
                ]
            ].to_dict("records"),
        )


def _build_test_events(symbols: list[str], signal_date: date) -> pd.DataFrame:
    """
    构造测试财报事件。

    :param symbols: 股票代码列表
    :param signal_date: 信号日期
    :return: 财报事件表
    """
    report_date = signal_date + timedelta(days=10)
    known_at = pd.Timestamp(signal_date - timedelta(days=5)).to_pydatetime()

    return pd.DataFrame(
        [
            {
                "event_id": f"TEST_{report_date:%Y%m%d}_{symbol}",
                "symbol": symbol,
                "report_date": report_date,
                "session": EarningsSession.AMC.value,
                "known_at": known_at,
                "status": "ESTIMATED",
                "source": "TEST",
            }
            for symbol in symbols
        ]
    )


def _build_simple_trading_days(signal_date: date) -> list[date]:
    """
    构造测试交易日历。

    :param signal_date: 信号日期
    :return: 交易日列表
    """
    begin_date = signal_date - timedelta(days=40)
    end_date = signal_date + timedelta(days=40)
    trading_days = []
    current_date = begin_date

    while current_date <= end_date:
        if current_date.weekday() < 5:
            trading_days.append(current_date)

        current_date += timedelta(days=1)

    return trading_days


if __name__ == "__main__":
    main()