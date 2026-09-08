#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 09:45
# software:Vscode
# brief : 财报驱动策略回测绩效统计

from math import sqrt

import pandas as pd


def calculate_max_drawdown(equity: pd.Series) -> float:
    """
    计算净值序列最大回撤。

    :param equity: 每日组合净值
    :return: 最大回撤，结果为非正小数
    """
    numeric_equity = pd.to_numeric(equity, errors="coerce").dropna()
    if numeric_equity.empty:
        return 0.0
    if (numeric_equity <= 0).any():
        raise ValueError("净值必须大于0")

    drawdown = numeric_equity / numeric_equity.cummax() - 1
    return float(drawdown.min())


def calculate_performance(
    equity_curve: pd.DataFrame,
    trade_count: int = 0,
    annual_trading_days: int = 252,
) -> dict[str, float | int]:
    """
    计算总收益、年化收益、波动率、夏普比率和最大回撤。

    夏普比率暂按无风险利率为零计算，实盘研究时可按市场币种调整。

    :param equity_curve: 包含equity字段的每日净值表
    :param trade_count: 回测成交笔数
    :param annual_trading_days: 每年交易日数量
    :return: 可序列化的绩效指标字典
    """
    if "equity" not in equity_curve.columns:
        raise ValueError("净值数据缺少equity字段")
    if trade_count < 0:
        raise ValueError("成交笔数不能小于0")
    if annual_trading_days <= 0:
        raise ValueError("annual_trading_days必须大于0")

    equity = pd.to_numeric(equity_curve["equity"], errors="coerce").dropna()
    if equity.empty:
        return {
            "initial_equity": 0.0,
            "final_equity": 0.0,
            "total_return": 0.0,
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe_ratio": 0.0,
            "maximum_drawdown": 0.0,
            "trade_count": trade_count,
        }
    if (equity <= 0).any():
        raise ValueError("净值必须大于0")

    period_count = max(len(equity) - 1, 0)
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1)
    annualized_return = (
        float((equity.iloc[-1] / equity.iloc[0]) ** (
            annual_trading_days / period_count
        ) - 1)
        if period_count > 0
        else 0.0
    )
    daily_returns = equity.pct_change().dropna()
    daily_volatility = float(daily_returns.std(ddof=1)) if len(daily_returns) > 1 else 0.0
    annualized_volatility = daily_volatility * sqrt(annual_trading_days)
    sharpe_ratio = (
        float(daily_returns.mean() / daily_volatility * sqrt(annual_trading_days))
        if daily_volatility > 0
        else 0.0
    )

    return {
        "initial_equity": float(equity.iloc[0]),
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe_ratio,
        "maximum_drawdown": calculate_max_drawdown(equity),
        "trade_count": trade_count,
    }
