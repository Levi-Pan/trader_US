
import threading
from datetime import datetime

from alpaca.data.enums import DataFeed
from alpaca.data.live import StockDataStream
from private_module.private_log import get_logger
from standard_module.config import (
    ALPACA_API_KEY,
    ALPACA_API_SECRET,
    ALPACA_DATA_FEED,
    SECTOR_ETFS,
)


market_lock = threading.Lock()
market_data = {
    symbol: {
        "symbol": symbol,
        "sector": sector,
        "price": None,
        "base_price": None,
        "change_pct": None,
        "updated_at": None,
    }
    for symbol, sector in SECTOR_ETFS.items()
}
logger = get_logger("market_stream")


def get_data_feed():
    """
    获取Alpaca行情类型

    :return: Alpaca DataFeed
    """
    if ALPACA_DATA_FEED.lower() == "sip":
        return DataFeed.SIP
    return DataFeed.IEX


async def trade_handler(trade):
    """
    处理Alpaca实时成交。

    :param trade: Alpaca 成交对象
    :return: 无
    """
    symbol = trade.symbol
    if symbol not in market_data:
        return

    with market_lock:
        row = market_data[symbol]
        if row["base_price"] is None:
            row["base_price"] = float(trade.price)

        row["price"] = float(trade.price)
        row["change_pct"] = (row["price"] / row["base_price"] - 1) * 100
        row["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_market_stream():
    """
    启动 Alpaca 实时行情连接。

    :return: 无
    """
    stream = StockDataStream(
        api_key=ALPACA_API_KEY,
        secret_key=ALPACA_API_SECRET,
        feed=get_data_feed(),
    )

    stream.subscribe_trades(trade_handler, *SECTOR_ETFS.keys())
    logger.info("订阅实时行情：%s", ",".join(SECTOR_ETFS.keys()))
    try:
        stream.run()
    except Exception:
        logger.error("Alpaca实时行情连接异常", exc_info=True)


def start_market_thread():
    """
    使用后台线程启动行情连接。

    :return: 后台线程
    """
    market_thread = threading.Thread(
        target=run_market_stream,
        name="alpaca_market_stream",
        daemon=True,
    )
    market_thread.start()
    return market_thread

def get_sector_snapshot():
    """
    获取板块实时行情快照。

    :return: 按涨幅降序排列的板块行情
    """
    with market_lock:
        rows = [dict(row) for row in market_data.values()]

    return sorted(
        rows,
        key=lambda row: (
            row["change_pct"] is None,
            -(row["change_pct"] or 0),
        ),
    )
