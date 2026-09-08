#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 09:26
# software:Vscode
# brief : 财报实际结果与一致预期差异判断

import math

from .models import SurpriseResult


def is_valid_number(value: float | int | None) -> bool:
    """
    判断输入是否为可用于计算的有限数值。

    :param value: 待判断数值
    :return: 有效有限数值返回True，否则返回False
    """
    if value is None or isinstance(value, bool):
        return False

    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def calculate_surprise_percent(
    actual_value: float | None,
    consensus_value: float | None,
) -> float | None:
    """
    计算实际值相对一致预期的预期差比例。

    :param actual_value: 财报实际值
    :param consensus_value: 公布前最后一次一致预期
    :return: 预期差比例，数据无效或一致预期为0时返回None
    """
    if not is_valid_number(actual_value):
        return None
    if not is_valid_number(consensus_value) or consensus_value == 0:
        return None

    return (float(actual_value) - float(consensus_value)) / abs(
        float(consensus_value)
    )


def classify_earnings_surprise(
    actual_eps: float | None,
    consensus_eps: float | None,
    actual_revenue: float | None = None,
    consensus_revenue: float | None = None,
) -> SurpriseResult:
    """
    根据EPS及可选营收数据判断财报是否超预期。

    EPS数据缺失时返回未知；营收两项均有效时，EPS和营收必须同时
    达标才视为超预期；营收数据不完整时仅使用EPS判断。

    :param actual_eps: 实际每股收益
    :param consensus_eps: 公布前最后一次一致预期每股收益
    :param actual_revenue: 实际营业收入
    :param consensus_revenue: 公布前最后一次一致预期营业收入
    :return: 财报预期差分类结果
    """
    if not is_valid_number(actual_eps) or not is_valid_number(consensus_eps):
        return SurpriseResult.UNKNOWN

    eps_beat = float(actual_eps) > float(consensus_eps)
    revenue_available = is_valid_number(actual_revenue) and is_valid_number(
        consensus_revenue
    )
    if not revenue_available:
        return SurpriseResult.BEAT if eps_beat else SurpriseResult.MISS

    revenue_beat = float(actual_revenue) >= float(consensus_revenue)
    if eps_beat and revenue_beat:
        return SurpriseResult.BEAT

    return SurpriseResult.MISS
