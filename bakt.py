#! /usr/bin/env python
# coding: utf-8

import logging.config
import os.path
import random
from argparse import ArgumentParser
from datetime import datetime, timedelta
from decimal import Decimal
from logging import getLogger
from typing import List

import pandas as pd

from constants import *
from models import Order, Position

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
trades = []  # type: List[dict]
positions = []
position_id = 0  # type: int
ZERO = Decimal(0)  # type: Decimal


def get_active_orders(dt: datetime) -> List[Order]:
    return [o for o in orders if o.is_active() and (dt - o.created_at).seconds >= delay_order_creation_sec]


def cancel_expired_orders(dt: datetime) -> None:
    for o in get_active_orders(dt):
        if (dt - o.created_at).seconds > order_expire_sec:
            o.cancel()


# def create_position(index: int, opened_at: datetime, side: str, price: float, amount: float, fee_rate: float) -> dict:
#     global position_id
#     position_id += 1
#     return {'id': position_id,
#             'open_index': index,
#             'side': side,
#             'amount': amount,
#             'opened_at': opened_at,
#             'open_price': price,
#             'open_fee': 0,
#             'open_amount': amount,
#             'close_index': None,
#             'closed_at': None,
#             'close_price': None,
#             'close_fee': 0,
#             'pnl': 0}


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
#     # TODO bitFlyerの損益計算に合わせる
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
                        o.contract(o.open_size)

                    # 注文量の一部が約定する場合
                    else:
                        # p = create_position(idx, exec_date, o.side, o.price, exec_size, 0.0)
                        position_id += 1
                        p = Position(position_id, exec_date, o.side, o.price, o.open_size, 0.0)
                        positions.append(p)
                        o.contract(exec_size)
                        # logger.debug(f"Partial contract, Created position [{p}]")

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
                            o.contract(order_size)
                            order_size = 0
                            # logger.debug(f"Partial contract, settlement position  [{p}]")

                        # 全て約定しきったためポジション解消する
                        else:

                            # 約定した量
                            open_amount = Decimal(p.open_amount)

                            # 注文の残量を更新
                            order_size = round(float(Decimal(order_size) - open_amount), 8)  # type: float

                            # 残りのポジションを全てクローズ
                            p.close(exec_date, exec_price, p.open_amount)

                            # 約定した量の分を注文に反映
                            o.contract(round(float(open_amount), 8))

                            # logger.debug(f"Full contract, settlement position [{p}]")

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

    order_id = 0  # type: int
    ltp = 0  # type: float

    if executions.empty:
        raise ValueError()

    executions['exec_date'] = pd.to_datetime(executions['exec_date'])

    start_time = executions.at[0, 'exec_date']
    logger.info(f"Start to trading. time: {start_time}")

    count = 0

    since = start_time
    until = since + timedelta(seconds=timeframe_sec)

    while True:

        logger.info(f"Start to trading. since {since} until {until}")

        # 現在時刻までの約定履歴を取得する
        new_executions = executions[
            (executions['exec_date'] >= since) & (executions['exec_date'] < until)]  # type: pd.DataFrame

        # 約定判定
        if new_executions.empty:
            logger.debug("New executions is empty.")
        else:
            for idx, e in new_executions.iterrows():
                contract(e, get_active_orders(until))
            ltp = float(new_executions.tail(1).iat[0, 3])

        # 注文キャンセル処理
        cancel_expired_orders(until)

        # シグナル探索&発注
        r = random.randint(0, 4)
        if r in [0]:
            # TODO 注文時の価格、量を取引戦略に基づいて決定するように変更する

            # 買い注文発行
            order_id += 1
            buy_order = Order(id=order_id, created_at=until, side=SIDE_BUY, _type=ORDER_TYPE_LIMIT, size=0.1,
                              price=ltp - 2)
            orders.append(buy_order)

            # 売り注文発行
            order_id += 1
            sell_order = Order(id=order_id, created_at=until, side=SIDE_SELL, _type=ORDER_TYPE_LIMIT, size=0.1,
                               price=ltp + 2)
            orders.append(sell_order)

        # 時間を進める
        since = until
        until = since + timedelta(seconds=timeframe_sec)

        count += 1
        if count > 1000:
            break

        logger.info(f"End trading.\n")


if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument('-f', '--file', required=False, action='store', dest='file', help='')
    args = parser.parse_args()

    if not os.path.exists(args.file):
        raise FileNotFoundError(f"File not found. [{args.file}]")

    data = pd.read_csv(args.file, dtype={'exec_date': 'str',
                                         'id': 'int',
                                         'side': 'str',
                                         'price': 'float',
                                         'size': 'float',
                                         'buy_child_order_acceptance_id': 'str',
                                         'sell_child_order_acceptance_id': 'str'})  # type: pd.DataFrame
    run(data)

    logger.debug('[Trades]')
    for t in trades:
        logger.debug(f"Trade -> {t}")

    print(f"Number of order: {len([o for o in orders if o.is_active()])}")
    print(f"Total order size: {round(float(sum([Decimal(o.size) for o in orders])), 8) if orders else 0}")
    print(f"Total pnl: {sum([t.pnl for t in trades])}")

    t_orders = pd.DataFrame(data={'id': [o.id for o in orders],
                                  'created_at': [o.created_at for o in orders],
                                  'side': [o.side for o in orders],
                                  'type': [o.type for o in orders],
                                  'price': [o.price for o in orders],
                                  'size': [o.size for o in orders],
                                  'status': [o.status for o in orders],
                                  'open_size': [o.open_size for o in orders]})
    # print(t_orders)
    # for t in trades:
    #     print("trade-> ", t)
