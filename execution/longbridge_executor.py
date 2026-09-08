#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/09/07 10:39
# software:Vscode
# brief : 将策略执行订单转换并提交至长桥模拟盘
import hashlib
import logging
from datetime import date
from decimal import Decimal

from longbridge_common import LongbridgePaperClient, OrderSide as LongbridgeOrderSide, OrderType, TimeInForceType

from strategy.models import OrderSide, PendingOrder

logger = logging.getLogger(__name__)

class LongbridgeExecutor:
    """长桥模拟盘订单执行器"""
    def __init__(self, dry_run:bool=True):
        """
        初始化长桥模拟盘订单执行器。

        :param client: 长桥模拟盘客户端
        """
        self.dry_run = dry_run
        self.client = LongbridgePaperClient()

    def submit_pending_order(self,order:PendingOrder,limit_price:float,):
        """
        将策略订单转换为长桥限价单并提交。

        :param order: trader_US策略生成的待执行订单
        :param limit_price: 委托限价
        :return: 长桥下单结果，演练模式返回None
        """
        self._validate_order(order,limit_price)
        symbol = self._normalize_symbol(order.symbol)
        broker_side = self._convert_side(order.side)
        client_request_id = self._build_client_request_id(order)
        if self.dry_run:
            logger.info(
                "模拟演练，不发送订单：symbol=%s, side=%s, "
                "quantity=%s, price=%s, request_id=%s",
                symbol,
                order.side.value,
                order.shares,
                limit_price,
                client_request_id,
            )
            return None
        
        response = self.client.orders.submit_order(symbol=symbol,order_type = OrderType.LO,side=broker_side,quantity=Decimal(str(order.shares)),time_in_force = TimeInForceType.Day,price = Decimal(str(limit_price)),client_request_id=client_request_id,remark=order.reason)
        logger.info( "长桥模拟盘订单提交成功：symbol=%s, order_id=%s",symbol,response.order_id,)
        return response
    
    @staticmethod
    def _validate_order(order: PendingOrder, limit_price: float):
        """
        校验待执行订单。

        :param order: 策略待执行订单
        :param limit_price: 委托限价
        :return: 无
        """
        if not order.symbol.strip():
            raise ValueError("股票代码不能为空")
        if order.shares <= 0:
            raise ValueError("委托股数必须大于0")
        if limit_price <= 0:
            raise ValueError("委托价格必须大于0")
        
    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """
        将策略股票代码转换为长桥股票代码。

        :param symbol: 策略股票代码
        :return: 长桥股票代码
        """
        normalized_symbol = symbol.strip().upper()
        if normalized_symbol.endswith(".US"):
            return normalized_symbol
        return f"{normalized_symbol}.US"
    
    @staticmethod
    def _convert_side(side: OrderSide):
        """
        转换策略买卖方向为长桥枚举。

        :param side: trader_US订单方向
        :return: 长桥订单方向
        """
        side_mapping = {OrderSide.BUY:LongbridgeOrderSide.Buy,OrderSide.SELL:LongbridgeOrderSide.Sell,}
        if side not in side_mapping:
            raise ValueError(f"不支持的订单方向: {side}")
        return side_mapping[side]
    
    @staticmethod
    def _build_client_request_id(order: PendingOrder) -> str:
        """
        生成可重复计算的防重复下单编号。

        :param order: 策略待执行订单
        :return: 防重复下单编号
        """
        request_source = (
            f"{order.event_id}|{order.execute_date:%Y%m%d}|"
            f"{order.symbol}|{order.side.value}"
        )
        request_hash = hashlib.sha256(
            request_source.encode("utf-8")
        ).hexdigest()
        return request_hash[:32]
    
    def cancel_order(self, order_id: str):
        """
        撤销长桥模拟盘订单。

        :param order_id: 长桥订单编号
        :return: 无
        """
        if self.dry_run:
            logger.info("模拟演练，不发送撤单：order_id=%s", order_id)
            return None
        return self.client.orders.cancel_order(order_id)
    
    def get_today_orders(self):
        """
        获取当天所有长桥模拟盘订单。

        :return: 长桥订单列表
        """
        return self.client.orders.get_today_orders()
    
    def get_position(self):
        """
        获取长桥模拟盘持仓。

        :return: 长桥持仓列表
        """
        return self.client.account.get_stock_positions()
    
    def get_account_balance(self):
        """
        获取长桥模拟盘账户资金。

        :return: 长桥账户资金信息
        """
        return self.client.account.get_balance()
    
    def get_last_price(self,symbol:str) ->float:
        """
        查询股票最新成交价
        ：param symbol:trader_US 股票代码’
        ：return： 最新成交价
        """
        normalized_symbol = self._normalize_symbol(symbol)
        quotes = self.client.market.get_quotes([normalized_symbol])
        if not quotes:
            raise RuntimeError(f"未查询到行情：{normalized_symbol}")
        last_price = float(quotes[0].last_done)
        if last_price <= 0:
            raise RuntimeError( f"行情价格无效：{normalized_symbol}, price={last_price}")
        logger.info("查询最新价成功：symbol=%s, price=%s",normalized_symbol,last_price,)
        return last_price

    def submit_pending_orders(self,pending_orders:list[PendingOrder]) -> list:
        """
        批量处理策略生成的待执行订单。

        :param pending_orders: 策略待执行订单列表
        :return: 成功提交的长桥订单结果列表
        """
        today=date.today()
        submitted_orders = []
        for order in pending_orders:
            if order.execute_date != today:
                logger.info("订单执行日期不是今天，跳过：""symbol=%s, execute_date=%s, today=%s",order.symbol,order.execute_date,today,)
                continue

            try:
                limit_price = order.reference_price
                if limit_price is None or limit_price <=0:
                    limit_price = self.get_last_price(order.symbol)
                
                response = self.submit_pending_order(order=order,limit_price=limit_price,)
                if response is not None:
                    submitted_orders.append(response)
            except Exception:
                logger.error("处理策略订单失败：symbol=%s, event_id=%s",order.symbol,order.event_id,exc_info=True,)

        logger.info("批量订单处理完成：待处理=%s, 已提交=%s, dry_run=%s",len(pending_orders),len(submitted_orders),self.dry_run,)
        return submitted_orders
    

    

