#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/10 14:42
# software:Vscode
# brief : 测试 Alpha Vantage 财报标准化结果

from datetime import datetime
import logging
import os
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from data_sources.alpha_vantage_fundamental import AlphaVantageFundamentalClient
from data_sources.fundamental_normalizer import normalize_alpha_vantage_fundamentals
from strategy.fundamental_factors import build_fundamental_candidates


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """
    测试 Alpha Vantage 财报标准化结果。

    :return: 无
    """
    symbol = "AAPL"
    client = AlphaVantageFundamentalClient()

    income_data = client.get_income_statement(symbol)
    balance_data = client.get_balance_sheet(symbol)
    cash_flow_data = client.get_cash_flow(symbol)

    fundamentals = normalize_alpha_vantage_fundamentals(
        income_data=income_data,
        balance_data=balance_data,
        cash_flow_data=cash_flow_data,
    )

    logger.info(
        "标准化完成：symbol=%s, rows=%s, columns=%s",
        symbol,
        len(fundamentals),
        list(fundamentals.columns),
    )

    if fundamentals.empty:
        logger.warning("标准化结果为空：symbol=%s", symbol)
        return

    latest = fundamentals.tail(1).iloc[0]

    logger.info(
        "最近一期财报：symbol=%s, fiscal_date_ending=%s, revenue=%s, net_income=%s, roe=%s, debt_ratio=%s",
        latest["symbol"],
        latest["fiscal_date_ending"],
        latest["revenue"],
        latest["net_income"],
        latest["roe"],
        latest["debt_ratio"],
    )

    candidates = build_fundamental_candidates(
        data=fundamentals,
        decision_time=datetime.now(),
        symbols=[symbol],
    )

    logger.info(
        "基本面候选测试完成：symbol=%s, candidates=%s",
        symbol,
        len(candidates),
    )


if __name__ == "__main__":
    main()