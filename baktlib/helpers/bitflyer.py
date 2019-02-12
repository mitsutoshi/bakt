# coding: utf-8

import pandas as pd


def conv_exec_to_ohlc(t: pd.DataFrame, rule: str) -> pd.DataFrame:
    t = t.set_index(pd.to_datetime(t['exec_date']))
    t['buy_size'] = t['size'].where(t['side'] == 'BUY', 0)
    t['sell_size'] = t['size'].where(t['side'] == 'SELL', 0)
    return t.resample(rule).agg({'price': 'ohlc',
                                 'size': 'sum',
                                 'buy_size': 'sum',
                                 'sell_size': 'sum',
                                 'buy_child_order_acceptance_id': 'nunique',
                                 'sell_child_order_acceptance_id': 'nunique'})
