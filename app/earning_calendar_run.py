#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/8/11 10:00
# software:Vscode
# brief : 下一周美股财报日历任务入口

import argparse
import os
import sys
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from earnings_calendar.calendar_service import run_earning_calendar
from private_module.private_log import get_logger


logger = get_logger("earning_calendar_run")


def parse_args():
    """
    解析启动参数。

    :return: 命令行参数对象
    """
    parser = argparse.ArgumentParser(description="获取下一周美股财报日历")
    parser.add_argument("--allow-any-day", action="store_true", help="允许非周一手工运行")
    parser.add_argument("--run-date", help="指定运行日期 YYYY-MM-DD，仅用于补跑或测试")
    return parser.parse_args()


def main():
    """
    执行财报日历入口。

    :return: 进程退出码
    """
    args = parse_args()
    run_date = (
        datetime.strptime(args.run_date, "%Y-%m-%d").date()
        if args.run_date
        else datetime.now().date()
    )
    return run_earning_calendar(run_date, args.allow_any_day)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.error("财报日历任务执行失败", exc_info=True)
        sys.exit(1)
