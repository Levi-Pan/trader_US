#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/9/5 09:45
# software:Vscode
# brief : 财报驱动量化策略包

"""财报驱动量化策略包。"""
from strategy.order_builder import build_buy_orders
from .stock_selector import select_daily_candidates