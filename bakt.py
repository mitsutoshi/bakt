#! /usr/bin/env python3
# coding: utf-8

import logging.config
import os.path
import time
from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from importlib import import_module
from logging import getLogger
from typing import List

import numpy as np
import pandas as pd

from baktlib import bktrepo, config
from baktlib.constants import *
from baktlib.helpers.calc import d, sub, sum_size
from baktlib.models import Order, Position
from baktlib.helpers import bitflyer

logging.config.fileConfig('./logging.conf', disable_existing_loggers=False)
logger = getLogger(__name__)
pd.options.display.width = 300
# pd.set_option('display.width', 300)
# pd.set_option('display.max_rows', 300)

DATETIME_F = '%Y-%m-%d %H:%M:%S'

trade_num = 1  # type: int
orders = []  # type: List[Order]
trades = []  # type: List[Position]
positions = []  # type: List[Position]
position_id = 0  # type: int
ZERO = Decimal('0')  # type: Decimal
t_orders = pd.DataFrame(data={'id': [],
                              'created_at': [],
                              'side': [],
                              'type': [],
                              'price': [],
                              'size': [],
                              'open_size': [],
                              'delay_sec': [],
                              'expire_sec': [],
                              'status': []})  # type: pd.DataFrame

# t_trades = pd.DataFrame(data={'id': [],
#                               'open_order_id': [],
#                               'opened_at': [],
#                               'side': [],
#                               'amount': [],
#                               'open_price': [],
#                               'open_amount': [],
#                               'open_fee': [],
#                               'closed_at': [],
#                               'close_price': [],
#                               'close_fee': [],
#                               'pnl': []},)  # type: pd.DataFrame

buy_pos_size = []
sell_pos_size = []
realized_pnl = []  # type: List[float]
unrealized_pnl = []  # type: List[float]
ltp_hst = []
buy_volume = []
sell_volume = []
times = []
his_orders = []  # type: List[Orders]
timeto = None  # type: datetime
exec_recv_delay_sec = []  # type: List[float]
order_delay_sec = []  # type: List[float]
volume = 0  # type: Decimal

# measurement
time_sum_unrealized_pnl = []
time_sum_current_pos_size = []
time_think = []
time_cancel = []
time_contract = []


def sum_current_pos_size() -> float:
    """保有中のポジションの量を返します。
    :return: 保有中のポジションの量
    """
    return round(float(sum([d(p.open_amount) for p in positions])), 8) if positions else 0.0


def sum_current_pos_size(side: str) -> float:
    open_amount = [d(p.open_amount) for p in positions if p.side == side]
    return round(float(sum(open_amount)), 8) if open_amount else 0.0


def sum_unrealized_pnl(ltp: float) -> int:
    """未実現損益の金額を返します。
    最終取引価格（ltp）に基づいて、保有中のポジションの未実現損益（含み損益）を計算して返します。
    :param ltp: 最終取引価格
    :return: 未実現損益
    """
    if not positions:
        return 0
    if positions[0].side == SIDE_BUY:
        pnl = [(d(ltp) - d(p.open_price)) * d(p.open_amount) for p in positions]
    elif positions[0].side == SIDE_SELL:
        pnl = [(d(p.open_price) - d(ltp)) * d(p.open_amount) for p in positions]
    return round(float(sum(pnl)))


def get_active_orders(dt: datetime) -> List[Order]:
    """有効な注文の一覧を返します。
    作成された注文が有効であるかの判断には、ステータスに加え、板乗りまでの時間も考慮します。
    作成されてから一定時間（delay_order_creation_sec）が経過した注文を有効と判断します。
    :param dt: 現在日時
    :return: 有効な注文の一覧
    """
    return [o for o in orders if o.status == 'ACTIVE' and (dt - o.created_at).total_seconds() >= o.delay_sec]


def contract(execution):

    exec_date = execution['exec_date']

    # 有効な注文のみを抽出
    active_orders = get_active_orders(exec_date.to_pydatetime())  # type: List[Order]
    if not active_orders:
        return

    global position_id
    contract_start = time.time()
    exec_price = float(execution['price'])
    exec_size = float(execution['size'])
    exec_side = execution['side']
    logger.debug(f"Start to execution -> id={execution['id']}, date={exec_date}, side={exec_side}, size={exec_size}, price={exec_price}")

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

            # TODO 成行の場合、注文サイズを満たす約定履歴を消化する前に、次の成行注文が発生してしまう可能性がある。
            # TODO 本来なら、発動すれば板を食って約定するものだが、シミュレーションのため状況が異なる。
            # TODO 成行の場合は、約定履歴は価格の参考のみにした方が良いかも。検討する。正確にやるなら板の情報がないと無理。
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
    time_contract.append(time.time() - contract_start)


def run(executions: pd.DataFrame):
    if executions.empty:
        raise ValueError(f"The data is empty.")

    global timeto
    global trade_num
    global t_orders
    global volume

    logger.info(f"Start to trading. number of executions: ")
    logger.info(f"Executions: length={len(executions):,}, from={executions.head(1).iat[0, 0]}, to={executions.tail(1).iat[0, 0]}")

    logger.info('start to_datetime exec_date')
    executions['exec_date'] = pd.to_datetime(executions['exec_date'])
    logger.info('end to_datetime exec_date')


    # 時間枠の切れ目に合わせて開始時刻を調整する
    print(executions.keys())
    first_exec_date = executions.at[0, 'exec_date']
    # first_exec_date = executions.head(1)['exec_date']
    # executions = executions.set_index('exec_date')

    # print(first_exec_date[0:4])
    # print(first_exec_date[5:7])
    # print(first_exec_date[8:10])
    # print(first_exec_date[11:13])
    # print(first_exec_date[14:16])
    # timefrom = datetime(year=int(first_exec_date[0:4]),
    #                     month=int(first_exec_date[5:7]),
    #                     day=int(first_exec_date[8:10]),
    #                     hour=int(first_exec_date[11:13]),
    #                     minute=int(first_exec_date[14:16]),
    #                     second=int(first_exec_date[17:19]),
    #                     tzinfo=timezone.utc)  # type: datetime

    timefrom = datetime(year=first_exec_date.year,
                        month=first_exec_date.month,
                        day=first_exec_date.day,
                        hour=first_exec_date.hour,
                        minute=first_exec_date.minute,
                        second=first_exec_date.second,
                        tzinfo=timezone.utc)  # type: datetime

    if timefrom.second % conf.timeframe_sec > 0:
        timefrom = timefrom - timedelta(seconds=timefrom.second % conf.timeframe_sec)

    timeto = timefrom + timedelta(seconds=conf.timeframe_sec)

    max_exec_date = executions.at[len(executions) - 1, 'exec_date']

    #
    print('read csv')
    rule = conf.user['ohlc_rule']
    ohlc = pd.read_csv('data/ohlc_bitflyer_20190326.csv')  # type: pd.DataFrame
    ohlc['time'] = pd.to_datetime(ohlc['time'])
    ohlc = ohlc.set_index('time').resample(rule=rule).agg({
                                         'open': 'first',
                                         'high': 'max',
                                         'low': 'min',
                                         'close': 'last',
                                         'size': 'sum',
                                         'delay': 'mean'})


    # ストラテジークラスをロードする
    tokens = conf.strategy.split('.')
    package_name = tokens[0]
    class_name = tokens[1]
    cls = getattr(import_module(package_name), class_name)
    stg = cls(conf.user, executions, ohlc)

    while trade_num <= conf.num_of_trade:

        if trade_num % 100 == 0:
            logger.info(f"Start to trading. No: {trade_num}, from {timefrom}, to: {timeto}")

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Start to trading. [No: {trade_num}, time: '{timefrom}' <= time < '{timeto}']")
            logger.debug("Orders:")
            logger.debug(f"  ACTIVE        : {len([o for o in orders if o.status == 'ACTIVE'])}")
            logger.debug(f"  CANCELED      : {len([o for o in orders if o.status == 'CANCELED'])}")
            logger.debug(f"  PARTIAL       : {len([o for o in orders if o.status == 'PARTIAL'])}")
            logger.debug(f"  COMPLETED     : {len([o for o in orders if o.status == 'COMPLETED'])}")
            logger.debug("Positions:")
            logger.debug(f"  length        : {len(positions)}")
            logger.debug(f"  size of buy   : {sum_current_pos_size('BUY')}")
            logger.debug(f"  size of sell  : {sum_current_pos_size('SELL')}")

        # 現在時刻までの約定履歴を取得する
        new_executions = executions[
            (executions['exec_date'] >= timefrom) & (executions['exec_date'] < timeto)]  # type: pd.DataFrame

        if not new_executions.empty:

            # 有効な注文が存在するなら約定判定する
            if get_active_orders(timeto):
                [contract(e) for idx, e in new_executions.iterrows()]

            ltp = new_executions.tail(1)['price'].values[0]

        # 注文キャンセル処理
        st_cancel = time.time()

        # 有効期限を過ぎた注文のステータスを有効期限切れに更新します。
        [o.cancel() for o in get_active_orders(timeto) if o.expire_sec and (timeto - o.created_at).total_seconds() > o.expire_sec]

        time_cancel.append(time.time() - st_cancel)

        # シグナル探索&発注
        st_think = time.time()
        new_orders = stg.think(trade_num, timeto, orders, positions)  # type: List[Order]
        time_think.append(time.time() - st_think)

        if new_orders:
            orders.extend(new_orders)

        # 時間枠ごとに状況を記録する
        times.append(timeto)
        buy_pos_size.append(sum_current_pos_size('BUY'))
        sell_pos_size.append(sum_current_pos_size('SELL'))
        realized_pnl.append(sum([t.pnl for t in trades]))
        unrealized_pnl.append(sum_unrealized_pnl(ltp))
        ltp_hst.append(ltp)
        buy_volume.append(round(float(new_executions[new_executions['side'] == 'BUY']['size'].sum()), 8))
        sell_volume.append(round(float(new_executions[new_executions['side'] == 'SELL']['size'].sum()) * -1, 8))
        his_orders.append(new_orders)
        exec_recv_delay_sec.append(new_executions['delay'].mean())
        order_delay_sec.append(sum([d(o.delay_sec) for o in new_orders]) / len(new_orders) if new_orders else 0.0)
        volume += Decimal(str(new_executions['size'].sum()))

        # 時間を進める
        timefrom = timeto
        timeto = timefrom + timedelta(seconds=conf.timeframe_sec)
        trade_num += 1
        logger.debug(f"End trading.\n")

        # 約定履歴データがこれ以上存在しない場合は、ループを終了する
        if timeto > max_exec_date:
            break


if __name__ == '__main__':

    try:
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
                                             'sell_child_order_acceptance_id': 'str',
                                             'delay': 'float'})  # type: pd.DataFrame
        print(data)

        # バックテスト実行
        run(data)

        executions_me = []  # type: List[Execution]
        for o in orders:
            executions_me.extend(o.executions)

        # クローズしたポジションを注文IDごとにグルーピングする
        t_trades = pd.DataFrame(data={'open_order_id': [t.open_order_id for t in trades],
                                      'pnl': [t.pnl for t in trades]})
        t_pnl_by_order = t_trades.groupby('open_order_id').sum()
        num_of_trades = len(t_pnl_by_order)
        num_of_win = len(t_pnl_by_order[t_pnl_by_order['pnl'] > 0])
        num_of_lose = len(t_pnl_by_order[t_pnl_by_order['pnl'] < 0])
        num_of_even = len(t_pnl_by_order[t_pnl_by_order['pnl'] == 0])
        win_rate = num_of_win / num_of_trades if num_of_trades else 0
        size_of_orders = round(float(sum([d(o.size) for o in orders])), 8) if orders else 0
        size_of_exec = float(sum([Decimal(e.size) for e in executions_me]))
        profit = round(sum([d(t.pnl) for t in trades if t.pnl > 0]))
        loss = abs(round(sum([d(t.pnl) for t in trades if t.pnl < 0])))
        avg_profit = profit / num_of_win if num_of_win else 0
        avg_loss = loss / (num_of_lose + num_of_even) if num_of_lose + num_of_even else 0
        expected_value = avg_profit * win_rate - avg_loss * (1 - win_rate)

        # テスト結果
        result = {

            # Conditions
            'datetime': datetime.now().strftime(DATETIME_F),
            'duration': time.time() - st,
            'exchange': conf.exchange,

            # Test Conditions
            'data_from': data.at[0, 'exec_date'].to_pydatetime().strftime(DATETIME_F),
            'data_to': timeto.strftime(DATETIME_F),
            'data_length': len(data),
            'timeframe_sec': conf.timeframe_sec,
            'num_of_timeframes': trade_num,
            'volume': float(volume),

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
            'avg_order_size': round(size_of_orders / len(orders), 8) if orders else 0,

            # Executions
            'num_of_exec': len(executions_me),
            'size_of_exec': size_of_exec,
            'price_of_exec': float(sum([Decimal(e.price) * Decimal(e.size) for e in executions_me])),
            'avg_exec_size': round(size_of_exec / len(executions_me), 8) if executions_me else 0,
            'exec_rate': round(size_of_exec / size_of_orders, 2) if size_of_orders else 0,
            # 注文サイズに対する約定サイズの割合（サイズに基づく約定率）
            'size_of_closed_exec': round(float(sum([Decimal(p.amount) for p in trades])), 8) if trades else 0,
            'size_of_unclosed_exec': round(float(sum([Decimal(p.open_amount) for p in positions])),
                                           8) if positions else 0,

            # history
            'last_prices': ltp_hst,
            'buy_pos_size': buy_pos_size,
            'sell_pos_size': sell_pos_size,
            'realized_gain': np.array(realized_pnl),
            'unrealized_gain': np.array(unrealized_pnl),
            'market_buy_size': buy_volume,
            'market_sell_size': sell_volume,
            # 'pnl_per_trade': [t.pnl for t in trades],
            'pnl_per_trade': t_pnl_by_order['pnl'].tolist(),
            'exec_recv_delay_sec': exec_recv_delay_sec,
            'order_delay_sec': order_delay_sec,

            # Stats
            'num_of_trades': num_of_trades,
            'num_of_win': num_of_win,
            'num_of_lose': num_of_lose,
            'num_of_even': num_of_even,
            'win_rate': win_rate,
            'profit': profit,
            'loss': loss,
            'expected_value': expected_value,
            'total_pnl': profit - loss,
            'pf': round(profit / loss, 2) if loss else 0.0
        }

        s = time.time()
        bktrepo.print_orders(orders)
        # bktrepo.print_executions(orders)
        # bktrepo.print_trades(trades)
        # bktrepo.print_positions(positions)
        bktrepo.print_graph(his_orders, result, conf.report_dst_dir)
        time_print = time.time() - s
        print(f"Time: {time.time() - st}")

    except Exception as e:
        logger.exception(e)
        raise e
