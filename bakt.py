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
from baktlib.helpers import bitflyer
from baktlib.helpers.calc import d, sub
from baktlib.models import Order, Position

logging.config.fileConfig('./logging.conf', disable_existing_loggers=False)
logger = getLogger(__name__)
pd.set_option('display.width', 300)

order_expire_sec = 2  # type: int
"""注文の有効時間（秒）"""

delay_order_creation_sec = 1  # type: float
"""注文が板乗りするまでの時間（秒）"""

timeframe_sec = 2  # type: int
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
time_think = []
time_cancel = []


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

            # 約定していないならスキップして次の注文を処理する
            if not buy_ok and not sell_ok:
                continue

            can_exec_size_by_order = min(o.open_size, exec_size)  # type: float

            # 保有中のポジションから決済対象となるポジションを抽出
            reverse_positions = [p for p in positions if (
                buy_ok and p.side == SIDE_SELL) or (sell_ok and p.side == SIDE_BUY)]

            # 決済対象のポジションが存在しない場合
            if not reverse_positions:

                position_id += 1
                positions.append(Position(position_id, exec_date, o.side, o.price, can_exec_size_by_order, 0.0, o.id))
                o.contract(exec_date, exec_price, can_exec_size_by_order)
                exec_size = sub(exec_size, can_exec_size_by_order)

            # 決済対象のポジションが存在する場合
            else:

                # ポジション決済処理
                for i, p in enumerate(positions):

                    # 注文と同じsideのポジションはスキップ
                    if (buy_ok and p.side == SIDE_BUY) or (sell_ok and p.side == SIDE_SELL):
                        continue

                    # ポジションの一部を決済
                    if p.open_amount - can_exec_size_by_order > 0:
                        p.close(exec_date, exec_price, can_exec_size_by_order)
                        o.contract(exec_date, exec_price, can_exec_size_by_order)
                        exec_size = sub(exec_size, can_exec_size_by_order)

                        # この注文と約定履歴の約定可能量を消化しきっているため、ゼロで更新
                        can_exec_size_by_order = 0

                    # ポジションの全部を決済
                    else:

                        # 約定履歴の持つ約定量からこのポジション決済によって、約定した分を減らす
                        exec_size = sub(exec_size, p.open_amount)

                        # この注文と約定履歴の約定可能量を更新
                        can_exec_size_by_order = sub(can_exec_size_by_order, p.open_amount)

                        # 約定した量の分を注文に反映
                        o.contract(exec_date, exec_price, p.open_amount)

                        # 残りのポジションを全てクローズ
                        p.close(exec_date, exec_price, p.open_amount)
                        trades.append(p)
                        del positions[i]

                    # 発注量を消化しきったらpositionsのループをbreakして次の注文の処理へ
                    if can_exec_size_by_order == 0:
                        break
        else:

            # TODO market注文対応
            raise ValueError('Not support order type of market.')

        # exec_sizeを消化しきっており、これ以上約定させられないため、処理を終了する
        if exec_size == 0:
            return


def run(executions: pd.DataFrame):
    logger.info(f"Start to trading. number of executions: ")
    logger.info(f"Executions:")
    logger.info(f"  number: {len(executions):,}")
    logger.info(f"  since: {executions.head(1).iat[0, 0]}")
    logger.info(f"  until: {executions.tail(1).iat[0, 0]}")

    if executions.empty:
        raise ValueError()

    executions['exec_date'] = pd.to_datetime(executions['exec_date'])
    since = executions.at[0, 'exec_date']
    until = since + timedelta(seconds=timeframe_sec)
    trade_num = 1  # type: int
    logger.info(f"Start to trading. time: {since}")

    while trade_num <= 1000:

        if trade_num % 100 == 0:
            logger.info(f"Start to trading. No: {trade_num}, Time: {until}")

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Start to trading. [No: {trade_num}, time: '{since}' <= time < '{until}']")
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
            [contract(e, get_active_orders(until)) for idx, e in new_executions.iterrows()]
            ltp = new_executions.tail(1)['price'].values[0]

        # 注文キャンセル処理
        st_cancel = time.time()
        cancel_expired_orders(until)
        time_cancel.append(time.time() - st_cancel)

        # シグナル探索&発注
        st_think = time.time()
        think(until, executions[executions['exec_date'] < until])
        time_think.append(time.time() - st_think)

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
        trade_num += 1
        logger.debug(f"End trading.\n")


def think(dt: datetime, executions: pd.DataFrame) -> None:
    ltp = float(executions.tail(1).iat[0, 3])  # type: float
    t = bitflyer.conv_exec_to_ohlc(executions, str(timeframe_sec) + 's').tail(2)
    # t['ls_diff'] = t['buy_size']['buy_size'] - t['sell_size']['sell_size']
    bs = t['buy_size'].values[0]
    ss = t['sell_size'].values[0]
    if bs > ss:
        ls = bs / ss * (bs + ss) if ss else 0.5
    elif bs < ss:
        ls = ss / bs * (bs + ss) * -1 if bs else 0.5
    else:
        ls = 0
    logger.debug(f"[think] {dt}, L/S Score: {ls}")

    psize = sum_current_pos_size()
    has_buy = positions and positions[0].side == 'BUY'
    has_sell = positions and positions[0].side == 'SELL'

    th = 100
    if ls >= th:
        orders.append(Order(id=get_order_id(),
                            created_at=dt,
                            side=SIDE_BUY,
                            _type=ORDER_TYPE_LIMIT,
                            size=1 + (psize if has_sell else 0),
                            price=ltp))
    elif ls <= -th:
        orders.append(Order(id=get_order_id(),
                            created_at=dt,
                            side=SIDE_SELL,
                            _type=ORDER_TYPE_LIMIT,
                            size=1 + (psize if has_buy else 0),
                            price=ltp))


if __name__ == '__main__':

    st = time.time()

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

    executions = []  # type: List[Execution]
    for o in orders:
        executions.extend(o.executions)

    print(f"Number of contracts: {len(executions)}")
    print(f"Total size of contracts: {float(sum([Decimal(e.size) for e in executions]))}")
    print(f"Number of trades: {len(trades) * 2}")
    print(f"Total order size: {round(float(sum([d(o.size) for o in orders])), 8) if orders else 0}")
    print(f"Total pnl: {sum([t.pnl for t in trades])}")

    # time
    print(f"time_sum_current_pos_size: {sum(time_sum_current_pos_size)}")
    print(f"time_sum_unrealized_pnl: {sum(time_sum_unrealized_pnl)}")
    print(f"time_think: {sum(time_think)}")
    print(f"time_cancel: {sum(time_cancel)}")

    print(f"Time: {time.time() - st}")
