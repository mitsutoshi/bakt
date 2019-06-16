# coding: utf-8

from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
import talib

from baktlib.models import Order, Position
from baktlib.strategy import Strategy


class TripleMACD(Strategy):

    def __init__(self,
                 user_config: Dict[str, Any],
                 executions: pd.DataFrame,
                 ohlc: pd.DataFrame):
        super().__init__(user_config, executions)
        self.order_delay_sec = float(self.user_config['order_delay_sec'])
        self.order_expire_sec = float(self.user_config['order_expire_sec'])
        self.order_size = float(self.user_config['order_size'])
        self.pos_limit_size = float(self.user_config['pos_limit_size'])
        self.ohlc = ohlc
        self.ema = talib.EMA(ohlc['close'], timeperiod=50)
        self.fastMACD = talib.MACD(ohlc['close'], fastperiod=6, slowperiod=19, signalperiod=9)
        self.middleMACD = talib.MACD(ohlc['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        pd.options.display.max_rows = 1000

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

        t = self.ohlc[self.ohlc.index < dt]
        if len(t) < 2:
            return []

        ltp = t.tail(1)['close'].values[0]
        fmacd = self.fastMACD[0]
        fsignal = self.fastMACD[1]
        mmacd = self.middleMACD[0]
        msignal = self.middleMACD[1]
        size = self.order_size

        if not (fmacd[trade_num - 1] and fmacd[trade_num] and fsignal[trade_num] and fsignal[trade_num - 1]):
            return []

        is_gc_fst = fmacd[trade_num] > fsignal[trade_num] and fmacd[trade_num - 1] <= fsignal[trade_num - 1]
        is_dc_fst = fmacd[trade_num] < fsignal[trade_num] and fmacd[trade_num - 1] >= fsignal[trade_num - 1]
        is_gc_mdl = mmacd[trade_num] > msignal[trade_num] and mmacd[trade_num - 1] <= msignal[trade_num - 1]
        is_dc_mdl = mmacd[trade_num] < msignal[trade_num] and mmacd[trade_num - 1] >= msignal[trade_num - 1]

        new_orders = []  # type: List[Order]
        if self.ema[trade_num] > 0 and (is_gc_fst or is_gc_mdl) and long_pos_size < self.pos_limit_size:
            new_orders.append(self.buy(t=dt, size=size + short_pos_size, price=ltp))
        elif self.ema[trade_num] < 0 and (is_dc_fst or is_dc_mdl) and short_pos_size < self.pos_limit_size:
            new_orders.append(self.sell(t=dt, size=size + long_pos_size, price=ltp))
        elif long_pos_size > 0 and (is_dc_fst or is_dc_mdl):
            new_orders.append(self.sell(t=dt, size=size + long_pos_size, price=ltp))
        elif short_pos_size > 0 and (is_gc_fst or is_gc_mdl):
            new_orders.append(self.buy(t=dt, size=size + short_pos_size, price=ltp))

        return new_orders
