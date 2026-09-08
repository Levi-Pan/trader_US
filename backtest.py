#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 09:27
# software:Vscode
# brief : 财报驱动策略离线回测命令行入口

import argparse
import json
import logging
import os

import pandas as pd

from strategy.data_loader import (
    load_earnings_calendar,
    load_earnings_results,
    load_fundamental_data,
    load_price_data,
)
from strategy.engine import BacktestEngine
from strategy.performance import calculate_performance


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """
    解析离线回测命令行参数。

    :return: 命令行参数对象
    """
    parser = argparse.ArgumentParser(description="运行财报驱动策略日线回测")
    parser.add_argument("--prices", required=True, help="日频行情CSV绝对路径")
    parser.add_argument("--fundamentals", required=True, help="基本面CSV绝对路径")
    parser.add_argument("--calendar", required=True, help="财报日历CSV绝对路径")
    parser.add_argument("--results", required=True, help="财报结果CSV绝对路径")
    parser.add_argument("--output-dir", required=True, help="回测结果输出绝对目录")
    parser.add_argument("--initial-cash", type=float, default=1_000_000.0)
    return parser.parse_args()


def run_backtest(args: argparse.Namespace) -> None:
    """
    读取输入数据、运行回测并保存结果。

    :param args: 命令行参数对象
    :return: 无返回值
    """
    if not os.path.isabs(args.output_dir):
        raise ValueError("output-dir必须使用绝对路径")

    engine = BacktestEngine(
        prices=load_price_data(args.prices),
        fundamentals=load_fundamental_data(args.fundamentals),
        earnings_results=load_earnings_results(args.results),
        events=load_earnings_calendar(args.calendar),
        initial_cash=args.initial_cash,
    )
    result = engine.run()
    os.makedirs(args.output_dir, exist_ok=True)
    result.equity_curve.to_csv(
        os.path.join(args.output_dir, "equity_curve.csv"),
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(
        [trade.__dict__ for trade in result.trades]
    ).to_csv(
        os.path.join(args.output_dir, "trades.csv"),
        index=False,
        encoding="utf-8-sig",
    )
    performance = calculate_performance(
        result.equity_curve,
        trade_count=len(result.trades),
    )
    with open(
        os.path.join(args.output_dir, "performance.json"),
        "w",
        encoding="utf-8",
    ) as performance_file:
        json.dump(performance, performance_file, ensure_ascii=False, indent=2)
    final_equity = (
        result.equity_curve.iloc[-1]["equity"]
        if not result.equity_curve.empty
        else result.final_cash
    )
    logger.info(
        "回测完成，成交数=%s，期末净值=%.2f，未平仓事件数=%s",
        len(result.trades),
        final_equity,
        len(result.open_positions),
    )


def main() -> None:
    """
    配置日志并启动离线回测。

    :return: 无返回值
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run_backtest(parse_args())


if __name__ == "__main__":
    main()
