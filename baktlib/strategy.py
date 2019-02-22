# coding: utf-8

from datetime import datetime
from logging import getLogger
from typing import List, Dict, Any

import pandas as pd

from baktlib.models import Order, Position


class Strategy(object):

    def __init__(self, user_config: Dict[str, Any], executions: pd.DataFrame):
        self.user_config = user_config  # type: Dict[str, Any]
        self.__order_id = 0
        self._logger = getLogger(__name__)
        self.executions = executions  # type: pd.DataFrame

    @property
    def next_order_id(self) -> int:
        self.__order_id += 1
        return self.__order_id

    def think(self,
              trade_num: int,
              dt: datetime,
              orders: List[Order],
              positions: List[Position],
              bids=None,
              asks=None) -> List[Order]:
        raise NotImplementedError
