# coding: utf-8

from datetime import datetime
from typing import List, Dict, Any

import pandas as pd

from baktlib.constants import *
from baktlib.models import Order, Position
from baktlib.strategy import Strategy


class Snake(Strategy):
    """
    価格の期間あたりのZスコアを算出して、異常値を検出したら逆張りでエントリーします。
    """

    def __init__(self,
                 user_config: Dict[str, Any],
                 executions: pd.DataFrame,
                 ohlc: pd.DataFrame):

        super().__init__(user_config, executions)

        # 約定履歴
        self.executions = executions  # type: pd.DataFrame

        # 注文遅延時間
        self.order_delay_sec = float(self.user_config['order_delay_sec'])

        # 注文有効時間
        self.order_expire_sec = float(self.user_config['order_expire_sec'])

        # 注文サイズ
        self.order_size = float(self.user_config['order_size'])

        # OHLC
        self.ohlc = ohlc

        w = int(self.user_config['window'])
        close = self.ohlc['price']['close']

        # 期間ごとの平均価格
        self.ohlc['mean'] = close.rolling(w, min_periods=1).mean()

        # 価格の偏差
        deviation = close - self.ohlc['mean']

        # 価格の標準偏差
        self.stdev = close.rolling(w, min_periods=1).std()

        # 価格のZスコア = 偏差（価格 - 母平均） / 標準偏差
        self.price_z = deviation / self.stdev

    def think(self,
              trade_num: int,
              dt: datetime,
              orders: List[Order],
              long_pos_size: float,
              short_pos_size: float,
              mid_price=None,
              best_ask_price=None,
              best_bid_price=None) -> List[Order]:

        new_orders = []  # type: List[Order]
        index = trade_num - 1
        if index >= len(self.ohlc):
            return []
        close = self.ohlc['price']['close'][index]
        delay = float(self.ohlc['delay']['delay'][index])
        print(f"{trade_num}, time: {self.ohlc.index[index]}, close: {close}, z: {self.price_z[index]}, "
              f"long_size: {long_pos_size}, short_size: {short_pos_size}, delay: {delay}")

        z_outside = 3.0  # type: float
        z_inside = 2.0  # type: float

        # if delay > 2 and long_size == 0 and short_size == 0:
        #     return new_orders

        z_prv = self.price_z[index]
        z_cur = self.price_z[index - 1]
        p2s = abs(self.stdev[index] * 2)
        p3s = abs(self.stdev[index] * 3)

        #
        # ポジションを保有している場合は利確のための注文を行う
        #

        if long_pos_size > 0:
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=Side.SELL, _type=ORDER_TYPE_LIMIT,
                                    size=long_pos_size, price=self.ohlc['mean'][index],
                                    delay_sec=self.order_delay_sec, expire_sec=self.order_expire_sec))
        elif short_pos_size > 0:
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=Side.BUY, _type=ORDER_TYPE_LIMIT,
                                    size=short_pos_size, price=self.ohlc['mean'][index],
                                    delay_sec=self.order_delay_sec, expire_sec=self.order_expire_sec))

        #
        # エントリー注文
        #

        # 逆張りで買い
        if -3 < z_cur < -2 and long_pos_size < float(self.user_config['pos_limit_size']):
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=Side.BUY, _type=ORDER_TYPE_LIMIT,
                                    size=self.order_size, price=self.ohlc['mean'][index] - p3s,
                                    delay_sec=self.order_delay_sec, expire_sec=self.order_expire_sec))

        if -2 < z_cur < -1.5 and long_pos_size < float(self.user_config['pos_limit_size']):
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=Side.BUY, _type=ORDER_TYPE_LIMIT,
                                    size=self.order_size, price=self.ohlc['mean'][index] - p2s,
                                    delay_sec=self.order_delay_sec, expire_sec=self.order_expire_sec))

        # 逆張りで売り
        if 2 > z_cur > 1.5 and short_pos_size < float(self.user_config['pos_limit_size']):
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=Side.SELL, _type=ORDER_TYPE_LIMIT,
                                    size=self.order_size, price=self.ohlc['mean'][index] + p2s,
                                    delay_sec=self.order_delay_sec, expire_sec=self.order_expire_sec))

        if 2 < z_cur < 3 and short_pos_size < float(self.user_config['pos_limit_size']):
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=Side.SELL, _type=ORDER_TYPE_LIMIT,
                                    size=self.order_size, price=self.ohlc['mean'][index] + p3s,
                                    delay_sec=self.order_delay_sec, expire_sec=self.order_expire_sec))
        return new_orders
