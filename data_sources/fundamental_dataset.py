#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/10 14:38
# software:Vscode
# brief : 构建 Alpha Vantage 基本面数据集

import logging
from typing import Sequence

import pandas as pd

from data_sources.alpha_vantage_fundamental import AlphaVantageFundamentalClient
from data_sources.fundamental_normalizer import normalize_alpha_vantage_fundamentals


logger = logging.getLogger(__name__)


def build_alpha_vantage_fundamental_dataset(
    symbols: Sequence[str],
    client: AlphaVantageFundamentalClient | None = None,
) -> pd.DataFrame:
    """
    构建 Alpha Vantage 基本面数据集。

    :param symbols: 股票代码列表
    :param client: Alpha Vantage 财报客户端
    :return: 标准化后的基本面数据集
    """
    if client is None:
        client = AlphaVantageFundamentalClient()

    normalized_symbols = _normalize_symbols(symbols)
    frames = []

    for index, symbol in enumerate(normalized_symbols, start=1):
        logger.info(
            "下载基本面数据：symbol=%s, progress=%s/%s",
            symbol,
            index,
            len(normalized_symbols),
        )

        try:
            income_data = client.get_income_statement(symbol)
            balance_data = client.get_balance_sheet(symbol)
            cash_flow_data = client.get_cash_flow(symbol)

            fundamentals = normalize_alpha_vantage_fundamentals(
                income_data=income_data,
                balance_data=balance_data,
                cash_flow_data=cash_flow_data,
            )

            if fundamentals.empty:
                logger.warning("基本面标准化结果为空：symbol=%s", symbol)
                continue

            frames.append(fundamentals)

        except Exception:
            logger.error(
                "基本面数据处理失败：symbol=%s",
                symbol,
                exc_info=True,
            )

    if not frames:
        return _empty_fundamental_dataset()

    return pd.concat(frames, ignore_index=True)


def _normalize_symbols(symbols: Sequence[str]) -> list[str]:
    """
    标准化股票代码列表。

    :param symbols: 原始股票代码列表
    :return: 去重后的股票代码列表
    """
    result = []

    for symbol in symbols:
        clean_symbol = str(symbol).strip().upper()

        if not clean_symbol:
            continue

        if clean_symbol.endswith(".US"):
            clean_symbol = clean_symbol[:-3]

        if clean_symbol not in result:
            result.append(clean_symbol)

    return result


def _empty_fundamental_dataset() -> pd.DataFrame:
    """
    创建空基本面数据集。

    :return: 空基本面数据集
    """
    return pd.DataFrame(
        columns=[
            "symbol",
            "report_date",
            "published_at",
            "fiscal_date_ending",
            "revenue",
            "net_income",
            "operating_cashflow",
            "capital_expenditures",
            "free_cashflow",
            "total_assets",
            "total_liabilities",
            "shareholder_equity",
            "roe",
            "debt_ratio",
            "revenue_growth",
            "profit_growth",
            "fcf_margin",
            "pe",
            "source",
        ]
    )