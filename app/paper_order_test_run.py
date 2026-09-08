#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/7 11:10
# software:Vscode
# brief :测试策略订单转换为长桥模拟盘订单

import logging
import os
import sys
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from execution import LongbridgeExecutor
from strategy.models import OrderSide, PendingOrder


logger = logging.getLogger(__name__)


def create_test_order() -> PendingOrder:
    """
    创建一笔手工测试订单。

    :return: 策略待执行订单
    """
    return PendingOrder(
        symbol="AAPL",
        event_id="MANUAL_TEST_AAPL",
        side=OrderSide.BUY,
        shares=1,
        signal_time=datetime.now(),
        execute_date=date.today(),
        reason="DRY_RUN_TEST",
        reference_price=100.0,
    )


# def main() -> None:
#     """
#     执行长桥模拟盘订单转换测试。

#     :return: 无
#     """
#     executor = LongbridgeExecutor(dry_run=True)
#     test_order = create_test_order()

#     executor.submit_pending_order(
#         order=test_order,
#         limit_price=100.0,
#     )
#     logger.info("订单转换测试完成，未向长桥发送订单")

def main() -> None:
    """
    批量测试策略订单执行流程。

    :return: 无
    """
    executor = LongbridgeExecutor(dry_run=True)
    pending_orders = [create_test_order()]

    executor.submit_pending_orders(pending_orders)

    logger.info("批量订单演练完成，未向长桥发送订单")

    
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    main()