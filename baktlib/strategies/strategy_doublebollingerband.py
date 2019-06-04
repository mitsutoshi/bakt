# coding: utf-8

from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
import talib

from baktlib.constants import *
from baktlib import bitflyer
from baktlib.calc import d
from baktlib.models import Order, Position
from baktlib.strategy import Strategy


class DoubleBollingerBand(Strategy):

    def __init__(self,
                 user_config: Dict[str, Any],
                 executions: pd.DataFrame):
        super().__init__(user_config, executions)

        self.timeperiod = 20
        self.ohlc_timeframe_sec = 10

        # 設定値を取得
        self.order_delay_sec = float(self.user_config['order_delay_sec'])
        self.order_expire_sec = float(self.user_config['order_expire_sec'])

        # 全約定履歴に対応するローソク足を作成
        self.ohlc = bitflyer.conv_exec_to_ohlc(executions, str(self.ohlc_timeframe_sec) + 's')  # type: pd.DataFrame

        # Nan値は直前の値に置換する
        self.ohlc = self.ohlc.fillna(method='ffill')
        print(f"Create {len(self.ohlc)} OHLC.")

        # Bollinger Bandを作成
        self.upp2, self.mid2, self.low2 = talib.BBANDS(
            self.ohlc['price']['close'], timeperiod=self.timeperiod, matype=talib.MA_Type.SMA, nbdevup=2, nbdevdn=2)
        self.upp3, self.mid3, self.low3 = talib.BBANDS(
            self.ohlc['price']['close'], timeperiod=self.timeperiod, matype=talib.MA_Type.SMA, nbdevup=3, nbdevdn=3)

    def think(self,
              trade_num: int,
              dt: datetime,
              orders: List[Order],
              positions: List[Position],
              bids=None,
              asks=None) -> List[Order]:

        new_orders = []  # type: List[Order]

        t = self.ohlc[self.ohlc.index < dt]
        if len(t) < self.timeperiod:
            return []

        ltp = t.tail(1)['price']['close'].values[0]
        buy_pos = [d(p.open_amount) for p in positions if p.side == 'BUY']
        sell_pos = [d(p.open_amount) for p in positions if p.side == 'SELL']
        buy_pos_size = round(float(sum(buy_pos)), 8) if buy_pos else 0.0
        sell_pos_size = round(float(sum(sell_pos)), 8) if sell_pos else 0.0
        recv_delay = float(t.tail(1)['delay'].values[0])
        # if recv_delay >= 1.5:
        #     return []
        c1 = t['price']['close'][-1]

        size = 0.15
        sign = None

        # Open long position
        if self.low3[trade_num - 1] <= c1 <= self.low2[trade_num - 1]:
            # if c1 < self.mid2[trade_num]:
            if buy_pos_size < float(self.user_config['pos_limit_size']):
                sign = 'buy'
                new_orders.append(Order(id=self.next_order_id, created_at=dt,
                                        side=SIDE_BUY,
                                        _type=ORDER_TYPE_LIMIT,
                                        size=size + sell_pos_size,
                                        price=ltp + 1,
                                        delay_sec=self.order_delay_sec,
                                        expire_sec=self.order_expire_sec))

        elif self.upp2[trade_num - 1] <= c1 <= self.upp3[trade_num - 1]:
            # elif c1 > self.mid2[trade_num]:
            if sell_pos_size < float(self.user_config['pos_limit_size']):
                sign = 'sell'
                new_orders.append(Order(id=self.next_order_id, created_at=dt,
                                        side=SIDE_SELL,
                                        _type=ORDER_TYPE_LIMIT,
                                        size=size + buy_pos_size,
                                        price=ltp - 1,
                                        delay_sec=self.order_delay_sec,
                                        expire_sec=self.order_expire_sec))

        print(f"No. {trade_num}  time={dt}, ohlc={t.tail(1).index.values[0]}, c1={c1}, sign={sign}, up2={self.upp2[trade_num]} up3={self.upp3[trade_num]}, lo2={self.low2[trade_num]}, lo3={self.low3[trade_num]}")

        return new_orders
