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

import strategy
from baktlib import bktrepo, config
from baktlib.constants import *
from baktlib.helpers.calc import d, sub, sum_size
from baktlib.models import Order, Position

logging.config.fileConfig('./logging.conf', disable_existing_loggers=False)
logger = getLogger(__name__)
pd.set_option('display.width', 300)
pd.set_option('display.max_rows', 300)
DATETIME_F = '%Y-%m-%d %H:%M:%S'

orders = []  # type: List[Order]
trades = []  # type: List[Position]
positions = []  # type: List[Position]
position_id = 0  # type: int
ZERO = Decimal('0')  # type: Decimal
# order_id = 0  # type: int

# history
buy_pos_size = []
sell_pos_size = []
realized_pnl = []  # type: List[float]
unrealized_pnl = []  # type: List[float]
ltp_hst = []
buy_volume = []
sell_volume = []
times = []
his_orders = []  # type: List[Orders]
until = None  # type: datetime

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
    """未実現損益の金額を返します。
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


# def get_order_id():
#     global order_id
#     order_id += 1
#     return order_id


def get_active_orders(dt: datetime) -> List[Order]:
    """有効な注文の一覧を返します。
    作成された注文が有効であるかの判断には、ステータスに加え、板乗りまでの時間も考慮します。
    作成されてから一定時間（delay_order_creation_sec）が経過した注文を有効と判断します。
    :param dt: 現在日時
    :return: 有効な注文の一覧
    """
    return [o for o in orders if o.is_active() and (dt - o.created_at).seconds >= o.delay_sec]


def cancel_expired_orders(dt: datetime) -> None:
    """有効期限を過ぎた注文のステータスを有効期限切れに更新します。
    :param dt: 現在日時
    """
    for o in [o for o in get_active_orders(dt) if o.expire_sec and (dt - o.created_at).seconds > o.expire_sec]:
        o.cancel()


def contract(execution, active_orders: List[Order]):
    global position_id
    exec_date = execution['exec_date']
    exec_price = float(execution['price'])
    exec_size = float(execution['size'])
    exec_side = execution['side']
    logger.debug(f"Execution: date={exec_date}, side={exec_side}, size={exec_size}, price={exec_price}")

    # TODO 成行の場合、注文サイズを満たす約定履歴を消化する前に、次の成行注文が発生してしまう可能性がある。
    # TODO 本来なら、発動すれば板を食って約定するものだが、シミュレーションのため状況が異なる。
    # TODO 成行の場合は、約定履歴は価格の参考のみにした方が良いかも。検討する。正確にやるなら板の情報がないと無理。

    for o in active_orders:

        if o.type == ORDER_TYPE_LIMIT:

            # 買い注文、売りテイク、約定価格が買い注文の指値以下の場合
            buy_ok = o.side == SIDE_BUY and exec_side == SIDE_SELL and exec_price <= o.price  # type: bool

            # 売り注文、買いテイク、約定価格が売り注文の指値以上の場合
            sell_ok = o.side == SIDE_SELL and exec_side == SIDE_BUY and exec_price >= o.price  # type: bool

            # 約定していないならスキップして次の注文を処理する
            if not buy_ok and not sell_ok:
                continue
        else:

            buy_ok = o.side == SIDE_BUY and exec_side == SIDE_SELL
            sell_ok = o.side == SIDE_SELL and exec_side == SIDE_BUY

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

        # exec_sizeを消化しきっており、これ以上約定させられないため、処理を終了する
        if exec_size == 0:
            return


def run(executions: pd.DataFrame):
    global until

    logger.info(f"Start to trading. number of executions: ")
    logger.info(f"Execution histories:")
    logger.info(f"  length: {len(executions):,}")
    logger.info(f"  from: {executions.head(1).iat[0, 0]}")
    logger.info(f"  to: {executions.tail(1).iat[0, 0]}")

    if executions.empty:
        raise ValueError()

    executions['exec_date'] = pd.to_datetime(executions['exec_date'])
    since = executions.at[0, 'exec_date']
    until = since + timedelta(seconds=conf.timeframe_sec)
    trade_num = 1  # type: int
    logger.info(f"Start to trading. time: {since}")

    while trade_num <= conf.num_of_trade:

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
        new_orders = strategy.think(trade_num, until, executions[executions['exec_date'] < until], positions,
                                    user_settings)
        if new_orders:
            orders.extend(new_orders)
        time_think.append(time.time() - st_think)

        # 時間枠ごとに状況を記録する
        times.append(until)
        buy_pos_size.append(sum_current_buy_pos_size())
        sell_pos_size.append(sum_current_sell_pos_size())
        realized_pnl.append(sum([t.pnl for t in trades]))
        unrealized_pnl.append(sum_unrealized_pnl(ltp))
        ltp_hst.append(ltp)
        buy_volume.append(round(float(new_executions[new_executions['side'] == 'BUY']['size'].sum()), 8))
        sell_volume.append(round(float(new_executions[new_executions['side'] == 'SELL']['size'].sum()) * -1, 8))
        his_orders.append(new_orders)

        # 時間を進める
        since = until
        until = since + timedelta(seconds=conf.timeframe_sec)
        trade_num += 1
        logger.debug(f"End trading.\n")


if __name__ == '__main__':

    st = time.time()

    # Parse arguments
    parser = ArgumentParser()
    parser.add_argument('-c', '--config', required=False, action='store', dest='config', help='')
    parser.add_argument('-f', '--file', required=False, action='store', dest='file', help='')
    args = parser.parse_args()

    # 引数で指定されたファイルが存在しない場合はエラーで終了させる
    if not os.path.exists(args.config):
        raise FileNotFoundError(f"File not found. [{args.config}]")
    if not os.path.exists(args.file):
        raise FileNotFoundError(f"File not found. [{args.file}]")

    # 設定ファイルを読み込む
    conf = config.Config(args.config)  # type: config.Config
    user_settings = {}  # type: dict
    for k, v in conf.user.items():
        user_settings.update({str(k): v})

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

    executions_me = []  # type: List[Execution]
    for o in orders:
        executions_me.extend(o.executions)

    # クローズしたポジションを注文IDごとにグルーピングする
    t_trades = pd.DataFrame(data={'open_order_id': [t.open_order_id for t in trades], 'pnl': [t.pnl for t in trades]})
    t_pnl_by_order = t_trades.groupby('open_order_id').sum()
    num_of_trades = len(t_pnl_by_order)
    num_of_win = len(t_pnl_by_order[t_pnl_by_order['pnl'] > 0])
    num_of_lose = len(t_pnl_by_order[t_pnl_by_order['pnl'] < 0])
    num_of_even = len(t_pnl_by_order[t_pnl_by_order['pnl'] == 0])
    size_of_orders = round(float(sum([d(o.size) for o in orders])), 8) if orders else 0
    size_of_exec = float(sum([Decimal(e.size) for e in executions_me]))
    profit = round(sum([d(t.pnl) for t in trades if t.pnl > 0]))
    loss = abs(round(sum([d(t.pnl) for t in trades if t.pnl < 0])))

    # テスト結果
    result = {

        # Conditions
        'datetime': datetime.now().strftime(DATETIME_F),
        'duration': time.time() - st,
        'exchange': conf.exchange,

        # Test Conditions
        'data_from': data.at[0, 'exec_date'].to_pydatetime().strftime(DATETIME_F),
        'data_to': until.strftime(DATETIME_F),
        'data_length': len(data),
        'timeframe_sec': conf.timeframe_sec,
        'num_of_timeframes': conf.num_of_trade,

        # Orders
        'num_of_orders': len(orders),
        'num_of_buy_orders': len([o for o in orders if o.side == SIDE_BUY]),
        'num_of_sell_orders': len([o for o in orders if o.side == SIDE_SELL]),
        'num_of_limit_orders': len([o for o in orders if o.type == ORDER_TYPE_LIMIT]),
        'num_of_market_orders': len([o for o in orders if o.type == ORDER_TYPE_MARKET]),
        'num_of_completed_orders': len([o for o in orders if o.status == ORDER_STATUS_COMPLETED]),
        'num_of_canceled_orders': len([o for o in orders if o.status == ORDER_STATUS_CANCELED]),
        'num_of_active_orders': len([o for o in orders if o.status == ORDER_STATUS_ACTIVE]),
        'size_of_orders': size_of_orders,
        'size_of_limit_orders': sum_size([o.size for o in orders if o.type == ORDER_TYPE_LIMIT]),
        'size_of_market_orders': sum_size([o.size for o in orders if o.type == ORDER_TYPE_MARKET]),
        'avg_order_size': 1,

        # Executions
        'num_of_exec': len(executions_me),
        'size_of_exec': size_of_exec,
        'price_of_exec': float(sum([Decimal(e.price) * Decimal(e.size) for e in executions_me])),
        'avg_exec_size': round(size_of_exec / len(executions_me), 8),
        'exec_rate': round(size_of_exec / size_of_orders, 2),  # 注文サイズに対する約定サイズの割合（サイズに基づく約定率）
        'size_of_closed_exec': round(float(sum([Decimal(p.amount) for p in trades])), 8),
        'size_of_unclosed_exec': round(float(sum([Decimal(p.open_amount) for p in positions])), 8),

        # history
        'last_prices': ltp_hst,
        'buy_pos_size': buy_pos_size,
        'sell_pos_size': sell_pos_size,
        'realized_gain': realized_pnl,
        'unrealized_gain': unrealized_pnl,
        'market_buy_size': buy_volume,
        'market_sell_size': sell_volume,
        'pnl_per_trade': [t.pnl for t in trades],

        # Stats
        'num_of_trades': num_of_trades,
        'num_of_win': num_of_win,
        'num_of_lose': num_of_lose,
        'num_of_even': num_of_even,
        'win_rate': num_of_win / num_of_trades if num_of_trades else 0,
        'profit': profit,
        'loss': loss,
        'total_pnl': profit - loss,
        'pf': round(profit / loss, 2)
    }

    s = time.time()
    bktrepo.print_orders(orders)
    bktrepo.print_executions(orders)
    bktrepo.print_trades(trades)
    bktrepo.print_positions(positions)
    bktrepo.print_graph(his_orders, result)
    time_print = time.time() - s

    print(f"Number of contracts: {len(executions_me)}")
    print(f"Total size of contracts: {float(sum([Decimal(e.size) for e in executions_me]))}")
    print(f"size_of_orders: {result['size_of_orders']}")
    print(f"size_of_exec: {result['size_of_exec']}")
    print(f"約定率: {round(result['size_of_exec'] / result['size_of_orders'], 2):.2%}")
    print(f"Number of trades: {num_of_trades}")
    print(f"Number of wins: {result['num_of_win']}")
    print(f"Number of lose: {result['num_of_lose']}")
    print(f"Number of even: {result['num_of_even']}")
    print(f"Win %: {result['win_rate']:%}")
    print(f"Closed of postion: {result['size_of_closed_exec']}")
    print(f"Unclosed position: {result['size_of_unclosed_exec']}")
    print(f"Total pnl: {sum([t.pnl for t in trades])}")
    print(f"time_sum_current_pos_size: {sum(time_sum_current_pos_size)}")
    print(f"time_sum_unrealized_pnl: {sum(time_sum_unrealized_pnl)}")
    print(f"time_think: {sum(time_think)}")
    print(f"time_cancel: {sum(time_cancel)}")
    print(f"time_print: {time_print}")
    print(f"Time: {time.time() - st}")
