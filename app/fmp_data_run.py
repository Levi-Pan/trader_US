#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 10:20
# software:Vscode
# brief : 下载FMP财报策略回测数据

import argparse
import csv
import logging
import os
import sys
from datetime import date


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from strategy.fmp_data import FmpClient, download_fmp_dataset, normalize_symbols


logger = logging.getLogger(__name__)


def parse_date(value: str) -> date:
    """
    解析YYYY-MM-DD格式日期。

    :param value: 日期字符串
    :return: 日期对象
    """
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须使用YYYY-MM-DD格式") from exc


def parse_args() -> argparse.Namespace:
    """
    解析FMP数据下载参数。

    :return: 命令行参数对象
    """
    parser = argparse.ArgumentParser(
        description="下载并生成财报策略回测所需的四份CSV"
    )
    parser.add_argument(
        "--symbols",
        help="逗号分隔股票代码，例如AAPL,MSFT,NVDA",
    )
    parser.add_argument(
        "--symbols-file",
        help="股票代码文本或CSV绝对路径",
    )
    parser.add_argument("--from", dest="start_date", required=True, type=parse_date)
    parser.add_argument("--to", dest="end_date", required=True, type=parse_date)
    parser.add_argument("--output-dir", required=True, help="标准CSV绝对输出目录")
    parser.add_argument(
        "--assumed-known-days",
        type=int,
        default=30,
        help="假设财报日期提前多少自然日被市场知晓，默认30",
    )
    parser.add_argument(
        "--unknown-session",
        choices=["AMC", "BMO", "TBD"],
        default="AMC",
        help="FMP缺少公布时段时的假设，默认按AMC处理",
    )
    parser.add_argument("--timeout", type=int, default=30, help="接口超时秒数")
    parser.add_argument("--retries", type=int, default=3, help="接口重试次数")
    return parser.parse_args()


def load_symbols(args: argparse.Namespace) -> list[str]:
    """
    从命令行或绝对路径文件读取股票代码。

    文本文件可每行一个代码，CSV优先读取symbol列。

    :param args: 命令行参数对象
    :return: 标准化股票代码列表
    """
    symbols = []
    if args.symbols:
        symbols.extend(args.symbols.split(","))
    if args.symbols_file:
        if not os.path.isabs(args.symbols_file):
            raise ValueError("symbols-file必须使用绝对路径")
        if not os.path.isfile(args.symbols_file):
            raise FileNotFoundError(f"股票池文件不存在：{args.symbols_file}")
        with open(
            args.symbols_file,
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as symbols_file:
            first_line = symbols_file.readline()
            symbols_file.seek(0)
            if "," in first_line:
                reader = csv.DictReader(symbols_file)
                normalized_fields = {
                    str(field).strip().lower(): field
                    for field in (reader.fieldnames or [])
                }
                if "symbol" not in normalized_fields:
                    raise ValueError("CSV股票池必须包含symbol字段")
                source_field = normalized_fields["symbol"]
                symbols.extend(row.get(source_field, "") for row in reader)
            else:
                symbols.extend(
                    line.strip() for line in symbols_file if line.strip()
                )
    return normalize_symbols(symbols)


def load_api_key() -> str:
    """
    从环境变量或本地配置读取FMP API Key。

    :return: FMP API Key
    """
    environment_key = os.environ.get("FMP_API_KEY", "").strip()
    if environment_key:
        return environment_key
    try:
        from standard_module.config import FMP_API_KEY
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "请设置FMP_API_KEY环境变量，或复制standard_module/"
            "config.example.py为config.py并填写FMP_API_KEY"
        ) from exc
    return str(FMP_API_KEY).strip()


def main() -> None:
    """
    下载并生成FMP标准回测数据。

    :return: 无返回值
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args()
    output_paths = download_fmp_dataset(
        client=FmpClient(
            api_key=load_api_key(),
            timeout=args.timeout,
            maximum_retries=args.retries,
        ),
        symbols=load_symbols(args),
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir,
        assumed_known_days=args.assumed_known_days,
        unknown_session=args.unknown_session,
    )
    logger.info("FMP回测数据生成完成，输出目录=%s", args.output_dir)
    for name, lpath in output_paths.items():
        logger.info("输出文件，类型=%s，路径=%s", name, lpath)


if __name__ == "__main__":
    main()
