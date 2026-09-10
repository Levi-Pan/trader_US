#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/10 14:48
# software:Vscode
# brief : 测试长桥日线行情数据集

import logging
import os
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from data_sources.longbridge_market_dataset import build_longbridge_daily_price_dataset
from strategy.technical_indicators import calculate_entry_features


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """
    测试长桥日线行情数据集。

    :return: 无
    """
    symbols = [
        "AAPL",
        "MSFT",
        "NVDA",
    ]

    prices = build_longbridge_daily_price_dataset(
        symbols=symbols,
        count=120,
    )

    logger.info(
        "长桥日线行情构建完成：symbols=%s, rows=%s",
        symbols,
        len(prices),
    )

    if prices.empty:
        logger.warning("长桥日线行情为空")
        return

    features = calculate_entry_features(prices)

    logger.info(
        "技术指标计算完成：rows=%s, columns=%s",
        len(features),
        list(features.columns),
    )

    logger.info(
        "最近行情：%s",
        features.tail(3)[["symbol", "date", "close", "ma20", "ma60", "volume_ratio", "atr_pct"]].to_dict("records"),
    )


if __name__ == "__main__":
    main()