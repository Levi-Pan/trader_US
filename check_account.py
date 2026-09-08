#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/6 10:14
# software:Vscode
# brief :查询长桥模拟盘账户资金

import logging
from longbridge_common import LongbridgePaperClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_account():
    """
    查询长桥模拟盘账户资金。

    :return: 无
    """
    client = LongbridgePaperClient()
    account_balance = client.trade.account_balance()
    logger.info("账户资金：%s", account_balance)

if __name__ == "__main__":
    check_account()