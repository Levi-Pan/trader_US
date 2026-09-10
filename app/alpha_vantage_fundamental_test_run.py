#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/10 10:12
# software:Vscode
# brief : 测试 Alpha Vantage 财报基础数据接口

import logging
import os
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from data_sources.alpha_vantage_fundamental import AlphaVantageFundamentalClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """
    测试 Alpha Vantage 财报基础数据接口。

    :return: 无
    """
    symbol = "AAPL"
    client = AlphaVantageFundamentalClient()

    income_data = client.get_income_statement(symbol)
    balance_data = client.get_balance_sheet(symbol)
    cash_flow_data = client.get_cash_flow(symbol)
    calendar_data = client.get_earnings_calendar(symbol=symbol)

    logger.info(
        "利润表获取成功：symbol=%s, quarterlyReports=%s, annualReports=%s",
        symbol,
        len(income_data.get("quarterlyReports", [])),
        len(income_data.get("annualReports", [])),
    )
    logger.info(
        "资产负债表获取成功：symbol=%s, quarterlyReports=%s, annualReports=%s",
        symbol,
        len(balance_data.get("quarterlyReports", [])),
        len(balance_data.get("annualReports", [])),
    )
    logger.info(
        "现金流量表获取成功：symbol=%s, quarterlyReports=%s, annualReports=%s",
        symbol,
        len(cash_flow_data.get("quarterlyReports", [])),
        len(cash_flow_data.get("annualReports", [])),
    )
    logger.info(
        "财报日历获取成功：symbol=%s, rows=%s",
        symbol,
        len(calendar_data),
    )


if __name__ == "__main__":
    main()