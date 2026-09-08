#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/09/05 08:57
# software:Vscode
# brief : 财报驱动策略统一参数配置

from dataclasses import dataclass
from math import isclose


@dataclass(frozen=True)
class StrategyConfig:
    """财报驱动策略配置。"""

    # 财报事件窗口
    candidate_lead_days: int = 10
    entry_deadline_days: int = 3
    add_deadline_days: int = 2

    # 基本面筛选
    fundamental_top_percent: float = 0.2

    # 分批建仓比例
    tranche_fractions: tuple[float, float, float] = (0.4, 0.3, 0.3)

    # 趋势指标
    short_ma_period: int = 20
    long_ma_period: int = 60
    ma_slope_lookback: int = 5

    # 成交量指标
    volume_ma_period: int = 20
    minimum_volume_ratio: float = 1.20

    # 波动率指标
    atr_period: int = 14
    maximum_atr_percent: float = 0.06

    # 仓位与止损
    risk_fraction: float = 0.005
    stop_atr_multiple: float = 2.50
    maximum_stock_weight: float = 0.05
    maximum_sector_weight: float = 0.20
    maximum_total_weight: float = 0.60
    maximum_adv_fraction: float = 0.01

    # 财报后PEAD持有时间
    maximum_post_earnings_days: int = 5

    # 交易成本，后续按实际券商修改
    commission_rate: float = 0.0
    slippage_bps: float = 5.0

    def __post_init__(self) -> None:
        """检查参数是否有效。"""

        if not 0 < self.fundamental_top_percent <= 1:
            raise ValueError(
                "fundamental_top_percent必须在0到1之间"
            )

        if not isclose(sum(self.tranche_fractions), 1.0):
            raise ValueError(
                "三次建仓比例之和必须等于1"
            )

        if any(
            fraction <= 0
            for fraction in self.tranche_fractions
        ):
            raise ValueError("建仓比例必须大于0")

        if self.entry_deadline_days >= self.candidate_lead_days:
            raise ValueError(
                "入场截止日必须晚于候选池生成日"
            )

        if self.add_deadline_days >= self.entry_deadline_days:
            raise ValueError(
                "加仓截止日必须晚于首次入场截止日"
            )

        if self.short_ma_period >= self.long_ma_period:
            raise ValueError(
                "短期均线周期必须小于长期均线周期"
            )

        if self.stop_atr_multiple <= 0:
            raise ValueError(
                "ATR止损倍数必须大于0"
            )

        ratio_fields = {
            "risk_fraction": self.risk_fraction,
            "maximum_stock_weight": self.maximum_stock_weight,
            "maximum_sector_weight": self.maximum_sector_weight,
            "maximum_total_weight": self.maximum_total_weight,
            "maximum_adv_fraction": self.maximum_adv_fraction,
        }
        if any(not 0 < value <= 1 for value in ratio_fields.values()):
            raise ValueError("仓位和风险比例必须在0到1之间")

        if self.maximum_stock_weight > self.maximum_total_weight:
            raise ValueError("单票仓位上限不能超过总仓位上限")

        if self.maximum_post_earnings_days < 0:
            raise ValueError("财报后持有天数不能小于0")

        if self.commission_rate < 0 or self.slippage_bps < 0:
            raise ValueError("交易成本参数不能小于0")


DEFAULT_CONFIG = StrategyConfig()
