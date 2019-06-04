# coding: utf-8

from datetime import datetime
from typing import List, Dict, Any

import pandas as pd

from baktlib.constants import *
from baktlib import bitflyer
from baktlib.calc import d
from baktlib.models import Order, Position
from baktlib.strategy import Strategy


class PriceFollow(Strategy):

    def __init__(self,
                 user_config: Dict[str, Any],
                 executions: pd.DataFrame):
        super().__init__(user_config, executions)
        self.order_delay_sec = float(self.user_config['order_delay_sec'])
        self.order_expire_sec = float(self.user_config['order_expire_sec'])
        self.ohlc = bitflyer.conv_exec_to_ohlc(executions, str(2) + 's')  # type: pd.DataFrame
        self.ohlc['lsdiff'] = self.ohlc['buy_size']['buy_size'] - self.ohlc['sell_size']['sell_size']
        print(f"Create {len(self.ohlc)} OHLC.")

    def think(self,
              trade_num: int,
              dt: datetime,
              orders: List[Order],
              positions: List[Position],
              bids=None,
              asks=None) -> List[Order]:

        new_orders = []  # type: List[Order]

        t = self.ohlc[self.ohlc.index < dt]
        if len(t) < 2:
            return []

        ltp = t.tail(1)['price']['close'].values[0]
        buy_pos = [d(p.open_amount) for p in positions if p.side == 'BUY']
        sell_pos = [d(p.open_amount) for p in positions if p.side == 'SELL']
        buy_pos_size = round(float(sum(buy_pos)), 8) if buy_pos else 0.0
        sell_pos_size = round(float(sum(sell_pos)), 8) if sell_pos else 0.0
        recv_delay = float(t.tail(1)['delay'].values[0])
        # recv_delay = 0

        lsdiff = t['lsdiff'].rolling(5, min_periods=5).sum().fillna(0)  # type: pd.Series
        v1 = lsdiff.values[-1]
        v2 = lsdiff.values[-2]
        print(f"No. {trade_num}  time={dt}, ohlc={t.tail(1).index.values[0]}, v1={v1}, v2={v2}")

        # if recv_delay >= 0.6:
        #     return []

        size = 0.1

        # Open long position
        th = 150
        if v1 > 0 > v2:
            if buy_pos_size < float(self.user_config['pos_limit_size']):
                [o.cancel() for o in orders if o.side == SIDE_SELL]
                # print(f"Buy {0.1 + (sell_pos_size if sell_pos_size > 0 else 0)}")
                new_orders.append(Order(id=self.next_order_id, created_at=dt,
                                        side=SIDE_BUY,
                                        _type=ORDER_TYPE_LIMIT,
                                        size=size + sell_pos_size,
                                        price=ltp - 10,
                                        delay_sec=self.order_delay_sec + recv_delay,
                                        expire_sec=self.order_expire_sec))

        # Open short position
        elif v1 < 0 < v2:
            if sell_pos_size < float(self.user_config['pos_limit_size']):
                # print(f"Sell {0.1 + (buy_pos_size if buy_pos_size > 0 else 0)}")
                [o.cancel() for o in orders if o.side == SIDE_BUY]
                new_orders.append(Order(id=self.next_order_id, created_at=dt,
                                        side=SIDE_SELL,
                                        _type=ORDER_TYPE_LIMIT,
                                        size=size + buy_pos_size,
                                        price=ltp + 10,
                                        delay_sec=self.order_delay_sec + recv_delay,
                                        expire_sec=self.order_expire_sec))

        # Close long position
        # elif buy_pos_size > 0 and v1 < th:
        #     #     print(f"Sell(exit) {buy_pos_size}")
        #     [o.cancel() for o in orders if o.side == SIDE_BUY]
        #     new_orders.append(Order(id=self.next_order_id, created_at=dt,
        #                             side=SIDE_SELL,
        #                             _type=ORDER_TYPE_LIMIT,
        #                             size=buy_pos_size,
        #                             price=ltp + 30,
        #                             delay_sec=self.order_delay_sec + recv_delay,
        #                             expire_sec=self.order_expire_sec))
        #
        # # Close short position
        # elif sell_pos_size > 0 and v1 > -th:
        #     # print(f"Buy(exit) {sell_pos_size}")
        #     [o.cancel() for o in orders if o.side == SIDE_SELL]
        #     new_orders.append(Order(id=self.next_order_id, created_at=dt,
        #                             side=SIDE_BUY,
        #                             _type=ORDER_TYPE_LIMIT,
        #                             size=sell_pos_size,
        #                             price=ltp - 30,
        #                             delay_sec=self.order_delay_sec + recv_delay,
        #                             expire_sec=self.order_expire_sec))
        return new_orders
