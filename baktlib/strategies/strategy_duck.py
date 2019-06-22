# coding: utf-8

from datetime import datetime
from typing import List, Dict, Any

import pandas as pd

from baktlib.models import Order, Position
from baktlib.strategy import Strategy


class Duck(Strategy):
    """
    Duck is trend follow strategy.
    
    Use MA deviation rate.
    """

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
        
        sema = self.ohlc['close'].ewm(span=6).mean()
        lema = self.ohlc['close'].ewm(span=19).mean()
        macd = sema - lema
        signal = macd.ewm(span=9).mean()
        histgram = macd - signal
        self.dev_rate = (histgram / signal).fillna(0)
        print('--- histgram ---')
        print(histgram.tail(10))
        print('--- signal ---')
        print(signal.tail(10))
        print('--- dev_rate ---')
        print(self.dev_rate.tail(10))

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
        size = self.order_size
        new_orders = []  # type: List[Order]
        cur = self.dev_rate[trade_num]
        prv = self.dev_rate[trade_num - 1]
        # print(f'cur={cur}, prv={prv}')
        
        if cur > 0:
            
            if cur > prv * 1.01 and cur < 1 and long_pos_size < self.pos_limit_size:
                
                # create long position
                new_orders.append(self.buy(t=dt, size=size, price=ltp))
                
            elif cur < prv and long_pos_size > 0:
                
                # close long position
                new_orders.append(self.sell(t=dt, size=long_pos_size, price=ltp))
            
        elif cur < 0:
        
            if cur < prv - prv * 0.01 and cur > -1 and short_pos_size < self.pos_limit_size:
                
                # create long position
                new_orders.append(self.sell(t=dt, size=size, price=ltp))
                
            elif cur > prv and short_pos_size > 0:
                
                # close short position
                new_orders.append(self.buy(t=dt, size=short_pos_size, price=ltp))
                
        return new_orders
