# coding: utf-8

import pandas as pd


def conv_exec_to_ohlc(t: pd.DataFrame, rule: str) -> pd.DataFrame:
    # t = t.set_index(pd.to_datetime(t['exec_date']))
    t['buy_size'] = t['size'].where(t['side'] == 'BUY', 0)
    t['sell_size'] = t['size'].where(t['side'] == 'SELL', 0)
    return t.resample(rule).agg({'price': 'ohlc',
                                 'size': 'sum',
                                 'buy_size': 'sum',
                                 'sell_size': 'sum',
                                 'buy_child_order_acceptance_id': 'nunique',
                                 'sell_child_order_acceptance_id': 'nunique',
                                 'delay': 'mean'}).fillna(method='ffill')


def create_ohlc_file_from_executions(input_file_path: str, output_file_path: str, rule: str = '1s'):
    executions = pd.read_csv(input_file_path, dtype={'exec_date': 'str',
                                                     'id': 'int',
                                                     'side': 'str',
                                                     'price': 'float',
                                                     'size': 'float',
                                                     'buy_child_order_acceptance_id': 'str',
                                                     'sell_child_order_acceptance_id': 'str',
                                                     'delay': 'float'})  # type: pd.DataFrame
    ohlc = conv_exec_to_ohlc(executions, rule)  # type: pd.DataFrame
    t = pd.DataFrame({
        'time': ohlc.index,
        'open': ohlc['price']['open'],
        'high': ohlc['price']['high'],
        'low': ohlc['price']['low'],
        'close': ohlc['price']['close'],
        'size': (ohlc['buy_size']['buy_size'] + ohlc['sell_size']['sell_size']).round(8),
        'delay': ohlc['delay']['delay'].round(3)})
    t = t.set_index(pd.to_datetime(t['exec_date']))
    t.fillna(method='ffill').to_csv(output_file_path, index=False, header=True)
    # print(t.head(100))


if __name__ == '__main__':
    import sys

    input_file_path = sys.argv[1]
    output_file_path = sys.argv[2]
    create_ohlc_file_from_executions(input_file_path=input_file_path,
                                     output_file_path=output_file_path,
                                     rule='1s')
