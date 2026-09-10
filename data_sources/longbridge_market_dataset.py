#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/10 14:45
# software:Vscode
# brief : 构建长桥日线行情数据集

from datetime import date
import logging
from typing import Any, Sequence

import pandas as pd

from longbridge_common import LongbridgePaperClient


logger = logging.getLogger(__name__)


def build_longbridge_daily_price_dataset(
    symbols: Sequence[str],
    count: int = 120,
    client: LongbridgePaperClient | None = None,
) -> pd.DataFrame:
    """
    构建长桥日线行情数据集。

    :param symbols: 股票代码列表
    :param count: 每只股票获取的日线数量
    :param client: 长桥模拟盘客户端
    :return: 标准化后的日线行情数据
    """
    if client is None:
        client = LongbridgePaperClient()

    request_symbols = _normalize_request_symbols(symbols)
    rows = []

    for index, request_symbol in enumerate(request_symbols, start=1):
        logger.info(
            "下载长桥日线行情：symbol=%s, progress=%s/%s",
            request_symbol,
            index,
            len(request_symbols),
        )

        try:
            bars = client.get_daily_bars(request_symbol, count=count)
        except Exception:
            logger.error(
                "长桥日线行情下载失败：symbol=%s",
                request_symbol,
                exc_info=True,
            )
            continue

        strategy_symbol = _to_strategy_symbol(request_symbol)

        for bar in bars:
            rows.append(_convert_daily_bar(strategy_symbol, bar))

    if not rows:
        return _empty_price_dataset()

    return pd.DataFrame(rows).sort_values(
        ["symbol", "date"],
        kind="stable",
    ).reset_index(drop=True)


def _convert_daily_bar(symbol: str, bar: Any) -> dict[str, Any]:
    """
    转换长桥日线行情字段。

    :param symbol: 策略股票代码
    :param bar: 长桥 K 线对象
    :return: 标准化日线行情
    """
    return {
        "symbol": symbol,
        "date": _parse_bar_date(bar),
        "open": float(bar.open),
        "high": float(bar.high),
        "low": float(bar.low),
        "close": float(bar.close),
        "volume": float(bar.volume),
    }


def _parse_bar_date(bar: Any) -> date:
    """
    解析长桥 K 线日期。

    :param bar: 长桥 K 线对象
    :return: 交易日期
    """
    timestamp = getattr(bar, "timestamp", None)

    if timestamp is not None:
        return pd.Timestamp(timestamp).date()

    trade_date = getattr(bar, "date", None)

    if trade_date is not None:
        return pd.Timestamp(trade_date).date()

    raise ValueError("长桥 K 线缺少 timestamp/date 字段")


def _normalize_request_symbols(symbols: Sequence[str]) -> list[str]:
    """
    标准化长桥请求股票代码列表。

    :param symbols: 原始股票代码列表
    :return: 去重后的长桥请求股票代码列表
    """
    result = []

    for symbol in symbols:
        clean_symbol = str(symbol).strip().upper()

        if not clean_symbol:
            continue

        if not clean_symbol.endswith(".US"):
            clean_symbol = f"{clean_symbol}.US"

        if clean_symbol not in result:
            result.append(clean_symbol)

    return result


def _to_strategy_symbol(symbol: str) -> str:
    """
    转换为策略内部股票代码。

    :param symbol: 长桥股票代码
    :return: 策略股票代码
    """
    clean_symbol = symbol.strip().upper()

    if clean_symbol.endswith(".US"):
        return clean_symbol[:-3]

    return clean_symbol


def _empty_price_dataset() -> pd.DataFrame:
    """
    创建空行情数据集。

    :return: 空行情数据集
    """
    return pd.DataFrame(
        columns=[
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    )