# coding: utf-8

from datetime import datetime
from typing import List, Dict, Any

import pandas as pd

from baktlib.constants import *
from baktlib.helpers import bitflyer
from baktlib.helpers.calc import d
from baktlib.models import Order, Position
from baktlib.strategy import Strategy


class Snake(Strategy):
    """
    価格の期間あたりのZスコアを算出して、異常値を検出したら逆張りでエントリーします。
    """

    def __init__(self,
                 user_config: Dict[str, Any],
                 executions: pd.DataFrame):
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
        rule = self.user_config['ohlc_rule']
        self.ohlc = bitflyer.conv_exec_to_ohlc(self.executions, rule=rule).fillna(method='ffill')

        w = int(self.user_config['window'])
        close = self.ohlc['price']['close']

        # 期間ごとの平均価格
        self.ohlc['mean'] = close.rolling(w, min_periods=1).mean()

        # 価格の偏差
        deviation = close - self.ohlc['mean']

        # 価格の標準偏差
        stdev = close.rolling(w, min_periods=1).std()

        # 価格のZスコア = 偏差（価格 - 母平均） / 標準偏差
        self.price_z = deviation / stdev

    def think(self,
              trade_num: int,
              dt: datetime,
              orders: List[Order],
              positions: List[Position],
              bids=None,
              asks=None) -> List[Order]:

        new_orders = []  # type: List[Order]
        index = trade_num - 1
        if index >= len(self.ohlc):
            return []
        close = self.ohlc['price']['close'][index]
        long_size, short_size = self.get_pos_size(positions)
        delay = float(self.ohlc['delay']['delay'][index])
        print(f"{trade_num}, time: {self.ohlc.index[index]}, close: {close}, z: {self.price_z[index]}, "
              f"long_size: {long_size}, short_size: {short_size}, delay: {delay}")

        profit = close * 0.0005

        # if delay > 1.5 and (self.price_z[index] > 1.5 or self.price_z[index] < -1.5):
        #
        #     if long_size >= 0.01:
        #         new_orders.append(Order(id=self.next_order_id,
        #                                 created_at=dt,
        #                                 side=SIDE_SELL,
        #                                 _type=ORDER_TYPE_LIMIT,
        #                                 size=long_size,
        #                                 price=close,
        #                                 delay_sec=self.order_delay_sec,
        #                                 expire_sec=self.order_expire_sec))
        #     elif short_size >= 0.01:
        #         new_orders.append(Order(id=self.next_order_id,
        #                                 created_at=dt,
        #                                 side=SIDE_BUY,
        #                                 _type=ORDER_TYPE_LIMIT,
        #                                 size=short_size,
        #                                 price=close,
        #                                 delay_sec=self.order_delay_sec,
        #                                 expire_sec=self.order_expire_sec))
        #     return new_orders

        # Zスコアが-3を下抜けしたら売り
        if self.price_z[index - 1] >= -3 and self.price_z[index] < -3:
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=SIDE_SELL,
                                    _type=ORDER_TYPE_LIMIT,
                                    size=self.order_size + long_size,
                                    price=close,
                                    delay_sec=self.order_delay_sec,
                                    expire_sec=self.order_expire_sec))

        elif self.price_z[index - 1] <= 3 and self.price_z[index] > 3:
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=SIDE_BUY,
                                    _type=ORDER_TYPE_LIMIT,
                                    size=self.order_size + short_size,
                                    price=close,
                                    delay_sec=self.order_delay_sec,
                                    expire_sec=self.order_expire_sec))

        # elif self.price_z[index - 1] < -3 and self.price_z[index] >= -3 and short_size > 0:
        #     new_orders.append(Order(id=self.next_order_id, created_at=dt, side=SIDE_BUY,
        #                             _type=ORDER_TYPE_LIMIT,
        #                             size=short_size,
        #                             price=close,
        #                             delay_sec=self.order_delay_sec,
        #                             expire_sec=self.order_expire_sec))
        #
        # elif self.price_z[index - 1] > 3 and self.price_z[index] <= 3 and long_size > 0:
        #     new_orders.append(Order(id=self.next_order_id, created_at=dt, side=SIDE_SELL,
        #                             _type=ORDER_TYPE_LIMIT,
        #                             size=long_size,
        #                             price=close,
        #                             delay_sec=self.order_delay_sec,
        #                             expire_sec=self.order_expire_sec))

        # Zスコアが負の閾値未満なら買い
        elif -3 < self.price_z[index] < -2:
            if long_size < float(self.user_config['pos_limit_size']):
                new_orders.append(Order(id=self.next_order_id,
                                        created_at=dt,
                                        side=SIDE_BUY,
                                        _type=ORDER_TYPE_LIMIT,
                                        size=self.order_size + short_size,
                                        price=close + 1,
                                        delay_sec=self.order_delay_sec,
                                        expire_sec=self.order_expire_sec))

        # Zスコアが正の閾値超なら
        elif 2 < self.price_z[index] < 3:
            if short_size < float(self.user_config['pos_limit_size']):
                new_orders.append(Order(id=self.next_order_id,
                                        created_at=dt,
                                        side=SIDE_SELL,
                                        _type=ORDER_TYPE_LIMIT,
                                        size=self.order_size + long_size,
                                        price=close - 1,
                                        delay_sec=self.order_delay_sec,
                                        expire_sec=self.order_expire_sec))

        # elif index > 0 and self.price_z[index - 1] < 1 <= self.price_z[index]:
        #     if long_size < float(self.user_config['pos_limit_size']):
        #         new_orders.append(Order(id=self.next_order_id,
        #                                 created_at=dt,
        #                                 side=SIDE_BUY,
        #                                 _type=ORDER_TYPE_LIMIT,
        #                                 size=self.order_size,
        #                                 price=close + 1,
        #                                 delay_sec=self.order_delay_sec,
        #                                 expire_sec=self.order_expire_sec))
        #
        # elif index > 0 and self.price_z[index - 1] > -1 > self.price_z[index]:
        #     if short_size < float(self.user_config['pos_limit_size']):
        #         new_orders.append(Order(id=self.next_order_id,
        #                                 created_at=dt,
        #                                 side=SIDE_SELL,
        #                                 _type=ORDER_TYPE_LIMIT,
        #                                 size=self.order_size,
        #                                 price=close - 1,
        #                                 delay_sec=self.order_delay_sec,
        #                                 expire_sec=self.order_expire_sec))

        return new_orders

    def get_pos_size(self, positions) -> (float, float):
        buy_pos = [d(p.open_amount) for p in positions if p.side == 'BUY']
        sell_pos = [d(p.open_amount) for p in positions if p.side == 'SELL']
        buy_size = round(float(sum(buy_pos)), 8) if buy_pos else 0.0
        sell_size = round(float(sum(sell_pos)), 8) if sell_pos else 0.0
        return buy_size, sell_size
