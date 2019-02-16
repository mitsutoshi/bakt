# coding: utf-8

import copy
from datetime import datetime
from logging import getLogger
from typing import List, Dict, Any

import pandas as pd

from baktlib.constants import *
from baktlib.helpers import bitflyer
from baktlib.helpers.calc import d
from baktlib.models import Order, Position

logger = getLogger(__name__)
order_id = 0  # type: int


class Strategy(object):

    def __init__(self, user_config: Dict[str, Any]):
        self.config = user_config  # type: Dict[str, Any]

    def think(self,
              trade_num: int,
              dt: datetime,
              executions: pd.DataFrame,
              positions: List[Position],
              user_settings: Dict[str, Any],
              bids=None,
              asks=None) -> List[Order]:
        raise NotImplementedError


def get_order_id():
    global order_id
    order_id += 1
    return order_id


def think(trade_num: int,
          dt: datetime,
          executions: pd.DataFrame,
          positions: List[Position],
          user_settings: Dict[str, Any],
          bids=None,
          asks=None) -> List[Order]:
    """

    :param trade_num: トレード番号
    :param dt: トレード日時
    :param executions: dt時点から見た過去の約定履歴
    :param positions: 現在有効なポジション
    :param user_settings:
    :param bids: 買い板（非対応）
    :param asks: 売り板（非対応）
    :return: 新規発行する注文のリスト
    """

    new_orders = []  # type: List[Order]
    ltp = float(executions.tail(1).iat[0, 3])  # type: float
    # current_pos_size = round(float(sum([d(p.open_amount) for p in positions])), 8) if positions else 0.0
    buy_pos_size = round(float(sum([d(p.open_amount) for p in positions if p.side == 'BUY'])), 8) if positions else 0.0
    sell_pos_size = round(float(sum([d(p.open_amount) for p in positions if p.side == 'SELL'])),
                          8) if positions else 0.0
    delay_sec = 0  # type: float

    # 約定履歴を1秒ごとにグルーピングする
    # 一定期間分遡ったボリューム差を合算する
    t = bitflyer.conv_exec_to_ohlc(executions, str(1) + 's').tail(10)  # type: pd.DataFrame
    size_diff = t['buy_size']['buy_size'] - t['sell_size']['sell_size']
    ls_diff_sum_5 = size_diff.rolling(5, min_periods=5).sum().fillna(0)  # type: pd.Series
    # print(ls_diff_sum_5)

    v1 = ls_diff_sum_5.values[-1]
    v2 = ls_diff_sum_5.values[-2]
    print(trade_num, v1, v2)

    # if diff_w_val < diff_m_val - diff_m_val * k:
    if v1 > 0 >= v2:
        if buy_pos_size < float(user_settings['pos_limit_size']):
            # print(f"Buy {0.1 + (sell_pos_size if sell_pos_size > 0 else 0)}")
            new_orders.append(Order(id=get_order_id(), created_at=dt,
                                    side=SIDE_BUY,
                                    _type=ORDER_TYPE_LIMIT,
                                    size=0.5 + (sell_pos_size if sell_pos_size > 0 else 0),
                                    price=ltp - 1,
                                    delay_sec=delay_sec,
                                    expire_sec=3))
        # else:
        #     logger.debug(f'Buy position limit over [{buy_pos_size}]')

    # elif diff_w_val > diff_m_val + diff_m_val * k:
    elif v1 < 0 <= v2:
        if sell_pos_size < float(user_settings['pos_limit_size']):
            # print(f"Sell {0.1 + (buy_pos_size if buy_pos_size > 0 else 0)}")
            new_orders.append(Order(id=get_order_id(), created_at=dt,
                                    side=SIDE_SELL,
                                    _type=ORDER_TYPE_LIMIT,
                                    size=0.5 + (buy_pos_size if buy_pos_size > 0 else 0),
                                    price=ltp + 1,
                                    delay_sec=delay_sec,
                                    expire_sec=3))

    elif v1 < v2 and buy_pos_size > 0:
    #     print(f"Sell(exit) {buy_pos_size}")
        new_orders.append(Order(id=get_order_id(), created_at=dt,
                                side=SIDE_SELL,
                                _type=ORDER_TYPE_LIMIT,
                                size=buy_pos_size,
                                price=ltp - 1,
                                delay_sec=delay_sec,
                                expire_sec=3))

    elif v1 > v2 and sell_pos_size > 0:
        # print(f"Buy(exit) {sell_pos_size}")
        new_orders.append(Order(id=get_order_id(), created_at=dt,
                                side=SIDE_BUY,
                                _type=ORDER_TYPE_LIMIT,
                                size=sell_pos_size,
                                price=ltp + 1,
                                delay_sec=delay_sec,
                                expire_sec=3))
    return new_orders
