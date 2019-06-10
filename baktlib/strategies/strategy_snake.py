# coding: utf-8

from datetime import datetime
from typing import List, Dict, Any

import pandas as pd

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

        super().__init__(user_config, None)

        self.ohlc = ohlc
        """OHLC"""

        w = int(self.user_config['window'])
        close = self.ohlc['price']['close']
        self.ohlc['mean'] = close.rolling(w, min_periods=1).mean()
        deviation = close - self.ohlc['mean']
        self.stdev = close.rolling(w, min_periods=1).std()
        self.price_z = deviation / self.stdev

    def think(self,
              trade_num: int,
              dt: datetime,
              orders: List[Order],
              positions: List[Position],
              long_pos_size: float,
              short_pos_size: float,
              ltp: float,
              mid_price=None,
              best_ask_price=None,
              best_bid_price=None) -> List[Order]:

        new_orders = []  # type: List[Order]
        index = trade_num - 1
        if index >= len(self.ohlc):
            return []

        #
        # エントリー注文
        #

        z_prv = self.price_z[index - 1]
        z_cur = self.price_z[index]
        m = self.ohlc['mean'][index]
        pos_lim_size = float(self.user_config['pos_limit_size'])

        #
        # ポジションを保有している場合は利確のための注文を行う
        #

        if long_pos_size > 0:

            if z_cur < -3.5:
                disposal_range = abs(self.stdev[index] * 2.5)  # type: float
            elif z_cur < -3:
                disposal_range = abs(self.stdev[index] * 2)  # type: float
            elif z_cur < -2.5:
                disposal_range = abs(self.stdev[index] * 1.5)  # type: float
            else:
                disposal_range = abs(self.stdev[index] * 0)  # type: float

            new_orders.append(self.sell(t=dt, size=long_pos_size, price=m - disposal_range))
            # return new_orders

            # order_size = long_pos_size
            # sell_orders = [o for o in orders if o.side == Side.SELL]
            # if sell_orders:
            #     order_size -= float(sum([Decimal(str(o.size)) for o in sell_orders]))
            # if order_size > 0:
            #     new_orders.append(self.sell(t=dt, size=order_size, price=self.ohlc['mean'][index] - disposal_range))

        elif short_pos_size > 0:

            if z_cur > 3.5:
                disposal_range = abs(self.stdev[index] * 2.5)  # type: float
            elif z_cur > 3:
                disposal_range = abs(self.stdev[index] * 2)  # type: float
            elif z_cur > 2.5:
                disposal_range = abs(self.stdev[index] * 1.5)  # type: float
            else:
                disposal_range = abs(self.stdev[index] * 0)  # type: float

            new_orders.append(self.buy(t=dt, size=short_pos_size, price=m + disposal_range))
            # return new_orders
            # order_size = short_pos_size
            # buy_orders = [o for o in orders if o.side == Side.BUY]
            # if buy_orders:
            #     order_size -= float(sum([Decimal(str(o.size)) for o in buy_orders]))
            # if order_size > 0:
            #     new_orders.append(self.buy(t=dt, size=order_size, price=self.ohlc['mean'][index] + disposal_range))

        # 逆張りで買い
        # if z_cur <= -2 and long_pos_size < float(self.user_config['pos_limit_size']):
        #     new_orders.append(self.buy(t=dt, size=self.order_size + long_pos_size * 2, price=m - abs(self.stdev[index] * (z_cur + 1))))
        # if -4.5 < z_cur <= -4 and long_pos_size < float(self.user_config['pos_limit_size']):
        #     new_orders.append(self.buy(t=dt, size=self.order_size, price=m - abs(self.stdev[index] * 4.5)))
        # if -4 < z_cur <= -3.5 and long_pos_size < float(self.user_config['pos_limit_size']):
        #     new_orders.append(self.buy(t=dt, size=self.order_size, price=m - abs(self.stdev[index] * 4)))
        # if -3.5 < z_cur <= -3 and long_pos_size < float(self.user_config['pos_limit_size']):
        #     new_orders.append(self.buy(t=dt, size=self.order_size, price=m - abs(self.stdev[index] * 3.5)))
        if -3 < z_cur <= -2.5 and long_pos_size < float(self.user_config['pos_limit_size']):
            new_orders.append(self.buy(t=dt, size=self.order_size, price=m - abs(self.stdev[index] * 3)))
        if -2.5 < z_cur <= -2 and long_pos_size < float(self.user_config['pos_limit_size']):
            new_orders.append(self.buy(t=dt, size=self.order_size, price=m - abs(self.stdev[index] * 2.5)))
        if -2 < z_cur <= -1.5 and long_pos_size < float(self.user_config['pos_limit_size']):
            new_orders.append(self.buy(t=dt, size=self.order_size, price=m - abs(self.stdev[index] * 2)))

        # 逆張りで売り
        # if 2 <= z_cur and short_pos_size < float(self.user_config['pos_limit_size']):
        #     new_orders.append(self.sell(t=dt, size=self.order_size + short_pos_size * 2, price=m + abs(self.stdev[index] * (z_cur + 1))))
        # if 4 <= z_cur < 4.5 and short_pos_size < float(self.user_config['pos_limit_size']):
        #     new_orders.append(self.sell(t=dt, size=self.order_size, price=m + abs(self.stdev[index] * 4.5)))
        # if 3.5 <= z_cur < 4 and short_pos_size < float(self.user_config['pos_limit_size']):
        #     new_orders.append(self.sell(t=dt, size=self.order_size, price=m + abs(self.stdev[index] * 4)))
        # if 3 <= z_cur < 3.5 and short_pos_size < float(self.user_config['pos_limit_size']):
        #     new_orders.append(self.sell(t=dt, size=self.order_size, price=m + abs(self.stdev[index] * 3.5)))
        if 2.5 <= z_cur < 3 and short_pos_size < float(self.user_config['pos_limit_size']):
            new_orders.append(self.sell(t=dt, size=self.order_size, price=m + abs(self.stdev[index] * 3)))
        if 2 <= z_cur < 2.5 and short_pos_size < float(self.user_config['pos_limit_size']):
            new_orders.append(self.sell(t=dt, size=self.order_size, price=m + abs(self.stdev[index] * 2.5)))
        if 1.5 <= z_cur < 2 and short_pos_size < float(self.user_config['pos_limit_size']):
            new_orders.append(self.sell(t=dt, size=self.order_size, price=m + abs(self.stdev[index] * 2)))

        return new_orders
