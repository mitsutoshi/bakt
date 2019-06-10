# coding: utf-8

from datetime import datetime
from logging import getLogger
from typing import List, Dict, Any

import pandas as pd

from baktlib.constants import ORDER_TYPE_LIMIT, Side
from baktlib.models import Order


class Strategy(object):

    def __init__(self, user_config: Dict[str, Any], executions: pd.DataFrame):
        self.user_config = user_config  # type: Dict[str, Any]
        self.__order_id = 0
        self._logger = getLogger(__name__)
        self.executions = executions  # type: pd.DataFrame

        self.order_delay_sec = float(self.user_config['order_delay_sec'])
        """注文遅延時間"""

        self.order_expire_sec = float(self.user_config['order_expire_sec'])
        """注文有効時間"""

        self.order_size = float(self.user_config['order_size'])
        """注文サイズ"""

    @property
    def next_order_id(self) -> int:
        self.__order_id += 1
        return self.__order_id

    def think(self,
              trade_num: int,
              dt: datetime,
              orders: List[Order],
              long_pos_size: float,
              short_pos_size: float,
              bids=None,
              asks=None) -> List[Order]:
        raise NotImplementedError

    def buy(self, t: datetime, size: float, price: float) -> Order:
        return Order(id=self.next_order_id, created_at=t, side=Side.BUY,
                     _type=ORDER_TYPE_LIMIT, size=size, price=price,
                     delay_sec=self.order_delay_sec, expire_sec=self.order_expire_sec)

    def sell(self, t: datetime, size: float, price: float) -> Order:
        return Order(id=self.next_order_id, created_at=t, side=Side.SELL,
                     _type=ORDER_TYPE_LIMIT, size=size, price=price,
                     delay_sec=self.order_delay_sec, expire_sec=self.order_expire_sec)
