#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 09:26
# software:Vscode
# brief : 财报策略趋势成交量与波动率指标计算

import pandas as pd

from .config import DEFAULT_CONFIG, StrategyConfig


OHLCV_COLUMNS = {"high", "low", "close", "volume"}


def validate_price_columns(data: pd.DataFrame) -> None:
    """
    检查技术指标所需的行情字段。

    :param data: 日频行情数据
    :return: 无返回值
    """
    missing_columns = OHLCV_COLUMNS - set(data.columns)
    if missing_columns:
        raise ValueError(f"行情数据缺少字段：{sorted(missing_columns)}")


def calculate_true_range(data: pd.DataFrame) -> pd.Series:
    """
    计算真实波幅。

    :param data: 已按交易日升序排列的单只股票行情
    :return: 与输入索引一致的真实波幅序列
    """
    validate_price_columns(data)
    previous_close = data["close"].shift(1)
    ranges = pd.concat(
        [
            data["high"] - data["low"],
            (data["high"] - previous_close).abs(),
            (data["low"] - previous_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1).rename("true_range")


def calculate_atr(
    data: pd.DataFrame,
    period: int = DEFAULT_CONFIG.atr_period,
) -> pd.Series:
    """
    使用简单移动平均计算ATR。

    :param data: 已按交易日升序排列的单只股票行情
    :param period: ATR计算周期
    :return: 与输入索引一致的ATR序列
    """
    if period <= 0:
        raise ValueError("ATR周期必须大于0")

    return calculate_true_range(data).rolling(
        window=period,
        min_periods=period,
    ).mean().rename(f"atr{period}")


def _calculate_symbol_features(
    data: pd.DataFrame,
    config: StrategyConfig,
) -> pd.DataFrame:
    """
    计算单只股票技术指标。

    :param data: 单只股票日频行情
    :param config: 策略参数
    :return: 增加技术指标后的行情数据
    """
    if "date" in data.columns:
        result = data.sort_values("date", kind="stable").copy()
    else:
        result = data.copy()
    numeric_columns = ["high", "low", "close", "volume"]
    result[numeric_columns] = result[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )

    result["ma20"] = result["close"].rolling(
        config.short_ma_period,
        min_periods=config.short_ma_period,
    ).mean()
    result["ma60"] = result["close"].rolling(
        config.long_ma_period,
        min_periods=config.long_ma_period,
    ).mean()
    result["ma20_slope"] = result["ma20"] - result["ma20"].shift(
        config.ma_slope_lookback
    )
    result["volume_ma20"] = result["volume"].rolling(
        config.volume_ma_period,
        min_periods=config.volume_ma_period,
    ).mean()
    result["volume_ratio"] = result["volume"].div(
        result["volume_ma20"].where(result["volume_ma20"] > 0)
    )
    result["atr14"] = calculate_atr(result, config.atr_period)
    result["atr_pct"] = result["atr14"].div(
        result["close"].where(result["close"] > 0)
    )
    result["dollar_volume"] = result["close"] * result["volume"]
    result["adv20_dollar"] = result["dollar_volume"].rolling(
        config.volume_ma_period,
        min_periods=config.volume_ma_period,
    ).mean()
    return result


def calculate_entry_features(
    data: pd.DataFrame,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    按股票计算入场和仓位管理需要的技术指标。

    :param data: 单只或多只股票的日频行情
    :param config: 策略参数
    :return: 增加均线、量比、ATR和成交额指标的行情数据
    """
    validate_price_columns(data)
    if data.empty:
        result = data.copy()
        for column in (
            "ma20",
            "ma60",
            "ma20_slope",
            "volume_ma20",
            "volume_ratio",
            "atr14",
            "atr_pct",
            "dollar_volume",
            "adv20_dollar",
        ):
            result[column] = pd.Series(dtype="float64")
        return result

    if "symbol" not in data.columns:
        return _calculate_symbol_features(data, config)

    frames = [
        _calculate_symbol_features(group, config)
        for _, group in data.groupby("symbol", sort=False, dropna=False)
    ]
    return pd.concat(frames).sort_index(kind="stable")
