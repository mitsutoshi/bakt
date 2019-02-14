# coding: utf-8

from datetime import datetime
from logging import getLogger
from typing import List

import pandas as pd

from baktlib.constants import *
from baktlib.helpers import bitflyer
from baktlib.helpers.calc import d
from baktlib.models import Order, Position

logger = getLogger(__name__)
order_id = 0  # type: int


def get_order_id():
    global order_id
    order_id += 1
    return order_id


def think(dt: datetime, executions: pd.DataFrame, positions: List[Position]) -> List[Order]:

    ltp = float(executions.tail(1).iat[0, 3])  # type: float
    current_pos_size = round(float(sum([d(p.open_amount) for p in positions])), 8) if positions else 0.0

    window = 5
    t = bitflyer.conv_exec_to_ohlc(executions, str(1) + 's').tail(window)  # type: pd.DataFrame
    ls_diff = t['buy_size']['buy_size'] - t['sell_size']['sell_size']
    ls_diff_5 = ls_diff.rolling(window, min_periods=window).sum().fillna(0)  # type: pd.Series
    ls = ls_diff_5.tail(1).values[0]
    logger.debug(f"[think] {dt}, L/S Score: {ls}")

    has_buy = positions and positions[0].side == 'BUY'
    has_sell = positions and positions[0].side == 'SELL'

    new_orders = []  # type: List[Order]
    th = 10
    if ls >= th:
        new_orders.append(Order(id=get_order_id(),
                                created_at=dt,
                                side=SIDE_SELL,
                                _type=ORDER_TYPE_LIMIT,
                                size=1 + (current_pos_size if has_sell else 0),
                                price=ltp))
    elif ls <= -th:
        new_orders.append(Order(id=get_order_id(),
                                created_at=dt,
                                side=SIDE_BUY,
                                _type=ORDER_TYPE_LIMIT,
                                size=1 + (current_pos_size if has_buy else 0),
                                price=ltp))
    return new_orders
