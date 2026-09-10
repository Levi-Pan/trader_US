#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/8 11:27
# software:Vscode
# brief :将选股结果转换并提交至长桥模拟盘执行器

import logging
import os
import sys
from datetime import date
from typing import Sequence

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from execution import LongbridgeExecutor
from strategy.order_builder import build_buy_orders


logger = logging.getLogger(__name__)


def get_selected_symbols() -> list[str]:
    """
    获取本次需要处理的选股结果。

    当前使用固定股票测试，后续替换为策略实际选股结果。

    :return: 选出的股票代码列表
    """
    return [
        "AAPL",
    ]


def run_paper_trade(
    selected_symbols: Sequence[str],
    shares_per_symbol: int = 1,
    dry_run: bool = True,
) -> list:
    """
    将选股结果转换为订单并交给长桥模拟盘执行器。

    :param selected_symbols: 策略选出的股票代码
    :param shares_per_symbol: 每只股票的测试买入股数
    :param dry_run: 是否仅演练而不发送订单
    :return: 成功提交的长桥订单结果列表
    """
    if not selected_symbols:
        logger.info("本次没有选出股票，不生成订单")
        return []

    pending_orders = build_buy_orders(
        selected_symbols=selected_symbols,
        execute_date=date.today(),
        shares_per_symbol=shares_per_symbol,
    )

    logger.info(
        "选股结果已转换为待执行订单：selected=%s, orders=%s",
        len(selected_symbols),
        len(pending_orders),
    )

    executor = LongbridgeExecutor(dry_run=dry_run)
    submitted_orders = executor.submit_pending_orders(pending_orders)

    logger.info(
        "模拟盘订单处理完成：pending=%s, submitted=%s, dry_run=%s",
        len(pending_orders),
        len(submitted_orders),
        dry_run,
    )
    return submitted_orders


def main() -> None:
    """
    启动长桥模拟盘订单执行流程。

    :return: 无
    """
    selected_symbols = get_selected_symbols()

    run_paper_trade(
        selected_symbols=selected_symbols,
        shares_per_symbol=1,
        dry_run=True,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    main()