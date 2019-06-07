# coding: utf-8

from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
import talib

from baktlib.calc import d
from baktlib.constants import *
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

        # rule = self.user_config['ohlc_rule']
        # self.ohlc = bitflyer.conv_exec_to_ohlc(executions, rule)  # type: pd.DataFrame
        # closes = self.ohlc['price']['close'].fillna(method='ffill')
        # print(f"Create {len(closes)} OHLC.")
        # self.ema = talib.EMA(closes, timeperiod=50)
        # self.fastMACD = talib.MACD(closes, fastperiod=6, slowperiod=19, signalperiod=9)
        # self.middleMACD = talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)

        self.ohlc = ohlc

        self.ema = talib.EMA(ohlc['close'], timeperiod=50)
        self.fastMACD = talib.MACD(ohlc['close'], fastperiod=6, slowperiod=19, signalperiod=9)
        self.middleMACD = talib.MACD(ohlc['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        pd.options.display.max_rows = 1000
        # print(self.fastMACD[0].head(1000))

    def think(self,
              trade_num: int,
              dt: datetime,
              orders: List[Order],
              positions: List[Position],
              mid_price=None,
              best_ask_price=None,
              best_bid_price=None) -> List[Order]:

        new_orders = []  # type: List[Order]

        t = self.ohlc[self.ohlc.index < dt]
        if len(t) < 2:
            return []

        ltp = t.tail(1)['close'].values[0]

        buy_pos = [d(p.open_amount) for p in positions if p.side == 'BUY']
        sell_pos = [d(p.open_amount) for p in positions if p.side == 'SELL']
        buy_pos_size = round(float(sum(buy_pos)), 8) if buy_pos else 0.0
        sell_pos_size = round(float(sum(sell_pos)), 8) if sell_pos else 0.0
        recv_delay = float(t.tail(1)['delay'].values[0])

        fmacd = self.fastMACD[0]
        fsignal = self.fastMACD[1]
        mmacd = self.middleMACD[0]
        msignal = self.middleMACD[1]
        size = self.order_size

        if not (fmacd[trade_num - 1] and fmacd[trade_num] and fsignal[trade_num] and fsignal[trade_num - 1]):
            return new_orders

        # print(f"fastmacd {fmacd[trade_num]}, signal: {fsignal[trade_num]}")
        is_gc_fast = fmacd[trade_num] > fsignal[trade_num] and fmacd[trade_num - 1] <= fsignal[trade_num - 1]
        is_dc_fast = fmacd[trade_num] < fsignal[trade_num] and fmacd[trade_num - 1] >= fsignal[trade_num - 1]
        is_gc_middle = mmacd[trade_num] > msignal[trade_num] and mmacd[trade_num - 1] <= msignal[trade_num - 1]
        is_dc_middle = mmacd[trade_num] < msignal[trade_num] and mmacd[trade_num - 1] >= msignal[trade_num - 1]

        # print(f"mid: {mid_price}")

        if self.ema[trade_num] > 0 and (is_gc_fast or is_gc_middle) and buy_pos_size < self.pos_limit_size:
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=Side.BUY,
                                    # _type=ORDER_TYPE_LIMIT, size=size + sell_pos_size, price=mid_price if mid_price else ltp,
                                    _type=ORDER_TYPE_LIMIT, size=size + sell_pos_size, price=ltp,
                                    delay_sec=self.order_delay_sec + recv_delay, expire_sec=self.order_expire_sec))

        elif self.ema[trade_num] < 0 and (is_dc_fast or is_dc_middle) and sell_pos_size < self.pos_limit_size:
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=Side.SELL,
                                    # _type=ORDER_TYPE_LIMIT, size=size + buy_pos_size, price=mid_price if mid_price else ltp,
                                    _type=ORDER_TYPE_LIMIT, size=size + buy_pos_size, price=ltp,
                                    delay_sec=self.order_delay_sec + recv_delay, expire_sec=self.order_expire_sec))

        elif buy_pos_size > 0 and (is_dc_fast or is_dc_middle):
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=Side.SELL,
                                    _type=ORDER_TYPE_LIMIT, size=buy_pos_size, price=ltp,
                                    delay_sec=self.order_delay_sec + recv_delay, expire_sec=self.order_expire_sec))

        elif sell_pos_size > 0 and (is_gc_fast or is_gc_middle):
            new_orders.append(Order(id=self.next_order_id, created_at=dt, side=Side.BUY,
                                    _type=ORDER_TYPE_LIMIT, size=sell_pos_size, price=ltp,
                                    delay_sec=self.order_delay_sec + recv_delay, expire_sec=self.order_expire_sec))

        return new_orders
