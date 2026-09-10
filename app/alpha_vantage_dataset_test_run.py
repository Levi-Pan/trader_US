#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/10 14:40
# software:Vscode
# brief : 测试 Alpha Vantage 多股票基本面数据集

from datetime import datetime
import logging
import os
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from data_sources.fundamental_dataset import build_alpha_vantage_fundamental_dataset
from strategy.fundamental_factors import build_fundamental_candidates


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """
    测试 Alpha Vantage 多股票基本面数据集。

    :return: 无
    """
    symbols = [
        "AAPL",
        "MSFT",
        "NVDA",
    ]

    fundamentals = build_alpha_vantage_fundamental_dataset(symbols)

    logger.info(
        "基本面数据集构建完成：symbols=%s, rows=%s",
        symbols,
        len(fundamentals),
    )

    candidates = build_fundamental_candidates(
        data=fundamentals,
        decision_time=datetime.now(),
        symbols=symbols,
    )

    logger.info(
        "基本面候选池生成完成：candidates=%s, symbols=%s",
        len(candidates),
        candidates["symbol"].tolist() if not candidates.empty else [],
    )


if __name__ == "__main__":
    main()