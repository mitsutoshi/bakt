#! /usr/bin/env python3
# coding: utf-8

import logging.config
import os.path
from argparse import ArgumentParser
from datetime import datetime, timedelta
from decimal import Decimal
from logging import getLogger
from typing import List

import pandas as pd
import time

from baktlib import bktrepo
from baktlib.constants import *
from baktlib.models import Order, Position

from baktlib.helpers import bitflyer

logging.config.fileConfig('./logging.conf', disable_existing_loggers=False)
logger = getLogger(__name__)
pd.set_option('display.width', 300)

order_expire_sec = 1  # type: int
"""注文の有効時間（秒）"""

delay_order_creation_sec = 0.0  # type: float
"""注文が板乗りするまでの時間（秒）"""

timeframe_sec = 1  # type: int
"""取引の時間間隔（秒）"""

orders = []  # type: List[Order]
trades = []  # type: List[Position]
positions = []  # type: List[Position]
position_id = 0  # type: int
ZERO = Decimal('0')  # type: Decimal
order_id = 0  # type: int

# history
buy_pos_size = []
sell_pos_size = []
realized_pnl = []  # type: List[float]
unrealized_pnl = []  # type: List[float]
ltp_hst = []
buy_volume = []
sell_volume = []

# measurement
time_sum_unrealized_pnl = []
time_sum_current_pos_size = []


def d(f: float) -> Decimal:
    """数値をDecimal型に変換して返します。
    :param f: 数値
    :return: Decimal(str(f))
    """
    return Decimal(str(f))


def sum_current_pos_size() -> float:
    """保有中のポジションの量を返します。
    :return: 保有中のポジションの量
    """
    s = time.time()
    val = round(float(sum([d(p.open_amount) for p in positions])), 8) if positions else 0.0
    time_sum_current_pos_size.append(float(d(time.time()) - d(s)))
    return val


def sum_current_buy_pos_size() -> float:
    s = time.time()
    val = round(float(sum([d(p.open_amount) for p in positions if p.side == SIDE_BUY])), 8) if positions else 0.0
    time_sum_current_pos_size.append(float(d(time.time()) - d(s)))
    return val


def sum_current_sell_pos_size() -> float:
    s = time.time()
    val = round(float(sum([d(p.open_amount) for p in positions if p.side == SIDE_SELL])), 8) if positions else 0.0
    time_sum_current_pos_size.append(float(d(time.time()) - d(s)))
    return val


def sum_unrealized_pnl(ltp: float) -> float:
    """未実現損益をの金額を返します。
    最終取引価格（ltp）に基づいて、保有中のポジションの未実現損益（含み損益）を計算して返します。
    :param ltp: 最終取引価格
    :return: 未実現損益
    """
    s = time.time()
    if not positions:
        return 0
    if positions[0].side == SIDE_BUY:
        pnl = [(d(ltp) - d(p.open_price)) * d(p.open_amount) for p in positions]
    elif positions[0].side == SIDE_SELL:
        pnl = [(d(p.open_price) - d(ltp)) * d(p.open_amount) for p in positions]
    val = round(float(sum(pnl)), 8)
    time_sum_unrealized_pnl.append(float(d(time.time()) - d(s)))
    return val


def get_order_id():
    global order_id
    order_id += 1
    return order_id


def get_active_orders(dt: datetime) -> List[Order]:
    return [o for o in orders if o.is_active() and (dt - o.created_at).seconds >= delay_order_creation_sec]


def cancel_expired_orders(dt: datetime) -> None:
    for o in get_active_orders(dt):
        if (dt - o.created_at).seconds > order_expire_sec:
            o.cancel()


# def close_position(idx, p: dict, exec_date, exec_price, exec_size):
#     logger.debug(f"[close_position] exec_size={exec_size}, open_amount={p['open_amount']}")
#     # クローズ済みの分を含むポジションの全体量
#     amount = Decimal(p['amount'])  # type: Decimal
#
#     # ポジションの現在のオープン量
#     open_amount = Decimal(p['open_amount'])  # type: Decimal
#
#     # クローズ価格
#     close_price = Decimal(exec_price)  # type: Decimal
#
#     # 過去の約定済み金額 = 約定価格 * 約定済みサイズ
#     past = Decimal(p['close_price']) * (amount - open_amount) if p[
#         'close_price'] else ZERO  # type: Decimal
#
#     # 約定総額 = 今回約定金額＋約定済み金額
#     current = close_price * open_amount
#
#     # 平均クローズ単価
#     avg_close_price = float((past + current) / amount)
#
#     # 損益計算
#     if p['side'] == SIDE_BUY:
#         current_pnl = (close_price - Decimal(p['open_price'])) * open_amount
#     elif p['side'] == SIDE_SELL:
#         current_pnl = (Decimal(p['open_price']) - close_price) * open_amount
#     else:
#         raise SystemError(f"Illegal value [side='{p['side']}'")
#
#     pnl = float(Decimal(p['pnl']) + current_pnl)
#
#     # 残りのオープンポジション量
#     remain_amount = round(float(open_amount - Decimal(exec_size)), 8)  # type: Decimal
#
#     # ポジションクローズ日時（オープンポジションがゼロになった場合のみ日時をセット）
#     closed_at = exec_date if remain_amount > 0 else None
#
#     p.update({'close_index': idx,
#               'open_amount': remain_amount,
#               'closed_at': closed_at,
#               'close_price': avg_close_price,
#               'close_fee': 0,
#               'pnl': pnl})

def contract(execution, active_orders: List[Order]):
    global position_id
    exec_date = execution['exec_date']
    exec_price = float(execution['price'])
    exec_size = float(execution['size'])
    exec_side = execution['side']
    logger.debug(f"Execution: date={exec_date}, side={exec_side}, size={exec_size}, price={exec_price}")

    for o in active_orders:

        if o.type == ORDER_TYPE_LIMIT:

            # 買い注文、売りテイク、約定価格が買い注文の指値以下の場合
            buy_ok = o.side == SIDE_BUY and exec_side == SIDE_SELL and exec_price <= o.price  # type: bool

            # 売り注文、買いテイク、約定価格が売り注文の指値以上の場合
            sell_ok = o.side == SIDE_SELL and exec_side == SIDE_BUY and exec_price >= o.price  # type: bool

            # アクティブな注文に対して約定が発生したか否か
            if buy_ok or sell_ok:

                # 保有中のポジションから決済対象となるポジションを抽出
                reverse_positions = [p for p in positions if (
                    buy_ok and p.side == SIDE_SELL) or (sell_ok and p.side == SIDE_BUY)]

                # 決済対象のポジションが存在しない場合
                if not reverse_positions:

                    # 注文量の全てが約定する場合
                    if exec_size >= o.open_size:

                        # p = create_position(idx, exec_date, o.side, o.price, o.open_size, 0.0)
                        position_id += 1
                        p = Position(position_id, exec_date, o.side, o.price, o.open_size, 0.0)

                        positions.append(p)
                        logger.debug(f"Created position [{p}, {o}]")

                        # TODO 約定量が多い場合、残った約定量を次の注文に適用する
                        # 約定量が注文量より多いのでこの注文は全て約定する
                        o.contract(exec_date, exec_price, o.open_size)
                        logger.debug(f"Full contract.")

                    # 注文量の一部が約定する場合
                    else:
                        position_id += 1
                        p = Position(position_id, exec_date, o.side, o.price, exec_size, 0.0)
                        positions.append(p)
                        o.contract(exec_date, exec_price, exec_size)
                        logger.debug(f"Partial contract.")

                # 決済対象のポジションが存在する場合
                else:

                    # この注文が現在処理中の約定に対して消化可能なサイズ
                    order_size = min(o.open_size, exec_size)  # type: float

                    # ポジション決済処理
                    for i, p in enumerate(positions):

                        # 注文と同じsideのポジションはスキップ
                        if (buy_ok and p.side == SIDE_BUY) or (sell_ok and p.side == SIDE_SELL):
                            continue

                        if p.open_amount - order_size > 0:

                            p.close(exec_date, exec_price, order_size)
                            logger.debug(f"Close position [{p}, {o}]")
                            o.contract(exec_date, exec_price, order_size)
                            order_size = 0
                            # logger.debug(f"Partial contract, settlement position  [{p}]")

                        # 全て約定しきったためポジション解消する
                        else:

                            # 約定した量
                            open_amount = d(p.open_amount)

                            # 注文の残量を更新
                            order_size = round(float(d(order_size) - open_amount), 8)  # type: float

                            # 残りのポジションを全てクローズ
                            p.close(exec_date, exec_price, p.open_amount)

                            # 約定した量の分を注文に反映
                            o.contract(exec_date, exec_price, round(float(open_amount), 8))

                            trades.append(p)

                            del positions[i]

                        # 発注量を消化しきったらbreak
                        if order_size == 0:
                            break

        else:
            raise ValueError('Not support order type of market.')


def run(executions: pd.DataFrame):
    logger.info(f"Start to trading. number of executions: ")
    logger.info(f"Executions:")
    logger.info(f"  number: {len(executions):,}")
    logger.info(f"  since: {executions.head(1).iat[0, 0]}")
    logger.info(f"  until: {executions.tail(1).iat[0, 0]}")

    if executions.empty:
        raise ValueError()

    executions['exec_date'] = pd.to_datetime(executions['exec_date'])
    start_time = executions.at[0, 'exec_date']
    logger.info(f"Start to trading. time: {start_time}")
    count = 0
    since = start_time
    until = since + timedelta(seconds=timeframe_sec)
    trade_num = 1  # type: int

    while True:
        logger.info(f"Start to trading. [No: {trade_num}, time: '{since}' <= time < '{until}']")
        logger.debug("Orders:")
        logger.debug(f"  ACTIVE        : {len([o for o in orders if o.status == ORDER_STATUS_ACTIVE])}")
        logger.debug(f"  CANCELED      : {len([o for o in orders if o.status == ORDER_STATUS_CANCELED])}")
        logger.debug(f"  PARTIAL       : {len([o for o in orders if o.status == ORDER_STATUS_PARTIAL])}")
        logger.debug(f"  COMPLETED     : {len([o for o in orders if o.status == ORDER_STATUS_COMPLETED])}")
        logger.debug("Positions:")
        logger.debug(f"  length        : {len(positions)}")
        logger.debug(f"  size of buy   : {sum_current_buy_pos_size()}")
        logger.debug(f"  size of sell  : {sum_current_sell_pos_size()}")

        # 現在時刻までの約定履歴を取得する
        new_executions = executions[
            (executions['exec_date'] >= since) & (executions['exec_date'] < until)]  # type: pd.DataFrame

        # 約定判定
        if new_executions.empty:
            logger.debug("New executions is empty.")
        else:
            for idx, e in new_executions.iterrows():
                contract(e, get_active_orders(until))

            ltp = new_executions.tail(1)['price'].values[0]

        # 注文キャンセル処理
        cancel_expired_orders(until)

        # シグナル探索&発注
        think(until, executions[executions['exec_date'] < until])

        # 時間枠ごとに状況を記録する
        buy_pos_size.append(sum_current_buy_pos_size())
        sell_pos_size.append(sum_current_sell_pos_size())
        realized_pnl.append(sum([t.pnl for t in trades]))
        unrealized_pnl.append(sum_unrealized_pnl(ltp))
        ltp_hst.append(ltp)
        buy_volume.append(round(float(new_executions[new_executions['side'] == 'BUY']['size'].sum()), 8))
        sell_volume.append(round(float(new_executions[new_executions['side'] == 'SELL']['size'].sum()) * -1, 8))

        # 時間を進める
        since = until
        until = since + timedelta(seconds=timeframe_sec)

        # FIXME
        trade_num += 1
        if trade_num > 180:
            break

        logger.info(f"End trading.\n")


def think(dt: datetime, executions: pd.DataFrame) -> None:
    ltp = float(executions.tail(1).iat[0, 3])  # type: float

    t = bitflyer.conv_exec_to_ohlc(executions.tail(1), str(timeframe_sec) + 's')
    t['ls_sub'] = t['buy_size']['buy_size'] - t['sell_size']['sell_size']
    # print(t)
    val = t['ls_sub'].values[0]

    psize = sum_current_pos_size()
    has_buy = positions and positions[0].side == 'BUY'
    has_sell = positions and positions[0].side == 'SELL'

    th = 0.6
    if val >= th:
        buy_order = Order(id=get_order_id(),
                          created_at=dt,
                          side=SIDE_BUY,
                          _type=ORDER_TYPE_LIMIT,
                          size=0.1 + (psize if has_sell else 0),
                          price=ltp)
        orders.append(buy_order)
    elif val <= -th:
        sell_order = Order(id=get_order_id(),
                           created_at=dt,
                           side=SIDE_SELL,
                           _type=ORDER_TYPE_LIMIT,
                           size=0.1 + (psize if has_buy else 0),
                           price=ltp)
        orders.append(sell_order)


if __name__ == '__main__':

    # Parse arguments
    parser = ArgumentParser()
    parser.add_argument('-f', '--file', required=False, action='store', dest='file', help='')
    args = parser.parse_args()

    # 引数で指定されたデータファイルが存在しない場合はエラーで終了させる
    if not os.path.exists(args.file):
        raise FileNotFoundError(f"File not found. [{args.file}]")

    # 約定履歴ファイルを読み込む
    data = pd.read_csv(args.file, dtype={'exec_date': 'str',
                                         'id': 'int',
                                         'side': 'str',
                                         'price': 'float',
                                         'size': 'float',
                                         'buy_child_order_acceptance_id': 'str',
                                         'sell_child_order_acceptance_id': 'str'})  # type: pd.DataFrame

    # バックテスト実行
    run(data)

    bktrepo.print_orders(orders)
    bktrepo.print_executions(orders)
    bktrepo.print_trades(trades)
    bktrepo.print_graph(data, trades, buy_pos_size, sell_pos_size, realized_pnl, unrealized_pnl, ltp_hst, buy_volume,
                        sell_volume)

    # order
    print(f"Number of order: {len(orders)}")
    print(f"Number of buy order: {len([o for o in orders if o.side == SIDE_BUY])}")
    print(f"Number of sell order: {len([o for o in orders if o.side == SIDE_SELL])}")
    print(f"Number of canceled order: {len([o for o in orders if o.status == ORDER_STATUS_CANCELED])}")
    print(f"Number of limit order: {len([o for o in orders if o.type == ORDER_TYPE_LIMIT])}")
    print(f"Number of market order: {len([o for o in orders if o.type == ORDER_TYPE_MARKET])}")

    print(f"Number of trades: {len(trades) * 2}")

    print(f"Total order size: {round(float(sum([d(o.size) for o in orders])), 8) if orders else 0}")
    print(f"Total pnl: {sum([t.pnl for t in trades])}")

    # time
    print(f"time_sum_current_pos_size: {sum(time_sum_current_pos_size)}")
    print(f"time_sum_unrealized_pnl: {sum(time_sum_unrealized_pnl)}")
