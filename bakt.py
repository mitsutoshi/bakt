#! /usr/bin/env python3
# coding: utf-8

import logging.config
import os.path
from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone
from importlib import import_module
from logging import getLogger
from typing import List

import pandas as pd
import time

from baktlib import bktrepo, config, bitflyer
from baktlib.calc import d, sub
from baktlib.constants import *
from baktlib.models import Order, OrderStatus, Side, OrderType
from baktlib.service import OrderManager, PositionManager, HistoryManager, TradeManager


def strg_cls(conf: config.Config):
    tokens = conf.strategy.split('.')
    pkg_name = tokens[0]
    cls_name = tokens[1]
    return getattr(import_module('baktlib.strategies.' + pkg_name), cls_name)


def can_buy(o: Order, exe_side: str, exe_price: float) -> bool:
    can = o.side == Side.BUY and exe_side == Side.SELL.value
    return can and exe_price <= o.price if o.type == OrderType.LIMIT.value else can


def can_sell(o: Order, exe_side: str, exe_price: float) -> bool:
    can = o.side == Side.SELL and exe_side == Side.BUY.value
    return can and exe_price >= o.price if o.type == OrderType.LIMIT.value else can


def contract(ex_date: pd.Timestamp, ex: pd.Series) -> None:
    # 有効な注文のみを抽出
    t = datetime(year=ex_date.year, month=ex_date.month, day=ex_date.day,
                 hour=ex_date.hour, minute=ex_date.minute, second=ex_date.second, tzinfo=timezone.utc)
    active_orders = order_mgr.get_active_orders(t)  # type: List[Order]
    if not active_orders:
        return

    e_size = ex['size']
    logger.debug(f"Start to execute: {ex['id']} {ex_date} {ex['side']} size={e_size}, price={ex['price']}")
    for o in active_orders:

        # TODO 成行の場合、注文サイズを満たす約定履歴を消化する前に、次の成行注文が発生してしまう可能性がある。
        # TODO 本来なら発動すれば板を食って約定するものだが、シミュのため状況が異なる。
        # TODO 成行は約定履歴は価格の参考のみにした方が良いかも。正確にやるなら板の情報がないと無理。
        # side別約定有無
        buy_ok = can_buy(o, ex['side'], ex['price'])  # type: bool
        sell_ok = can_sell(o, ex['side'], ex['price'])  # type: bool

        # 約定していないならスキップして次の注文を処理する
        if not buy_ok and not sell_ok:
            continue

        # 約定可能サイズ
        can_exec_size_by_order = min(o.open_size, e_size)  # type: float

        # 保有中のポジションから決済対象となるポジションを抽出
        reverse_positions = pos_mgr.filter(side=Side.SELL if buy_ok else Side.BUY)

        # 決済対象のポジションが存在しない場合
        if not reverse_positions:
            pos_mgr.add_position(ex_date, o, can_exec_size_by_order, 0.0)
            o.contract(ex_date, ex['price'], can_exec_size_by_order)
            e_size = sub(e_size, can_exec_size_by_order)

        # 決済対象のポジションが存在する場合
        else:

            # ポジション決済処理
            for i, p in enumerate(pos_mgr.get()):

                # 注文と同じsideのポジションはスキップ
                if (buy_ok and p.side == SIDE_BUY) or (sell_ok and p.side == SIDE_SELL):
                    continue

                # ポジションの一部を決済
                if p.open_amount - can_exec_size_by_order > 0:
                    p.close(ex_date, ex['price'], can_exec_size_by_order)
                    o.contract(ex_date, ex['price'], can_exec_size_by_order)
                    e_size = sub(e_size, can_exec_size_by_order)

                    # この注文と約定履歴の約定可能量を消化しきっているため、ゼロで更新
                    can_exec_size_by_order = 0

                # ポジションの全部を決済
                else:

                    # 約定履歴の持つ約定量からこのポジション決済によって、約定した分を減らす
                    e_size = sub(e_size, p.open_amount)

                    # この注文と約定履歴の約定可能量を更新
                    can_exec_size_by_order = sub(can_exec_size_by_order, p.open_amount)

                    # 約定した量の分を注文に反映
                    o.contract(ex_date, ex['price'], p.open_amount)

                    # 残りのポジションを全てクローズ
                    p.close(ex_date, ex['price'], p.open_amount)
                    trd_mgr.add_trade(p)
                    pos_mgr.delete_positions(i)

                # 発注量を消化しきったらpositionsのループをbreakして次の注文の処理へ
                if can_exec_size_by_order == 0:
                    break

        # e_sizeを消化しきっており、これ以上約定させられないため、処理を終了する
        if e_size == 0:
            return


def run():
    # データファイル読み込み
    exec = pd.read_csv(args.file, dtype=DTYPES_EXEC)  # type: pd.DataFrame
    boards = pd.read_csv(args.boards, dtype=DTYPES_BOARDS)  # type: pd.DataFrame
    logger.info(f"Executions: len={len(exec):,}, from={exec.head(1).iat[0, 0]}, to={exec.tail(1).iat[0, 0]}")

    # 約定日時をPandsのdatetime型に変換してインデックスに設定
    logger.info('start to_datetime exec_date')
    exec['exec_date'] = pd.to_datetime(exec['exec_date'])
    logger.info('end to_datetime exec_date')

    # トレードの時間枠の先頭
    head = exec.at[0, 'exec_date']
    _from = datetime(year=head.year, month=head.month, day=head.day,
                     hour=head.hour, minute=head.minute, second=head.second, tzinfo=timezone.utc)  # type: datetime
    if _from.second % conf.timeframe_sec > 0:
        _from = _from - timedelta(seconds=_from.second % conf.timeframe_sec)

    # トレードの時間枠の終端
    to = _from + timedelta(seconds=conf.timeframe_sec)

    exec = exec.set_index('exec_date')

    # 約定履歴のデータからOHLC作成
    ohlc = bitflyer.conv_exec_to_ohlc(exec, rule=conf.user['ohlc_rule'])  # type: pd.DataFrame
    ohlc['close'] = ohlc['price']['close']

    # ストラテジークラスをロードする
    stg = strg_cls(conf)(conf.user, exec, ohlc)

    trade_num = 1  # type: int
    while trade_num <= conf.num_of_trade:
        if trade_num % 100 == 0:
            logger.info(f"Start to trading. No: {trade_num}, from {_from}, to: {to}")
        if logger.isEnabledFor(logging.DEBUG):
            a = len(order_mgr.get(status=OrderStatus.ACTIVE))
            c = len(order_mgr.get(status=OrderStatus.CANCELED))
            p = len(order_mgr.get(status=OrderStatus.PARTIAL))
            m = len(order_mgr.get(status=OrderStatus.COMPLETED))
            logger.debug(f"[Trading] No={trade_num},from='{_from}',to='{to}' "
                         f"[Order] ACTIVE={a},CANCELED={c},PARTIAL={p},COMPLETED={m}, [Position] len={pos_mgr.len()},"
                         f"buy_size={pos_mgr.sum_size(side=Side.BUY)},sell_size={pos_mgr.sum_size(side=Side.SELL)} ")

        # 現在時刻までの約定履歴を取得する
        new_exec = exec[(exec.index >= _from) & (exec.index < to)]  # type: pd.DataFrame
        if not new_exec.empty:

            # 新しい約定履歴と有効な注文が存在するなら約定判定を行う
            if order_mgr.get_active_orders(to):
                [contract(idx, e) for idx, e in new_exec.iterrows()]  # TODO Executionのオブジェクトで渡したらどうか？

            # 最終約定価格を最新の価格に更新
            ltp = new_exec.tail(1)['price'].values[0]

        # 有効期限を過ぎた注文をキャンセルする
        order_mgr.cancel(to)

        # 取引時間帯の板を抽出
        next_time = to + timedelta(seconds=1)
        s_time = boards['time'].str[:19]
        b = boards[(s_time >= to.strftime(DATETIME_F)) & (s_time < next_time.strftime(DATETIME_F))]

        # ストラテジーを実行してシグナル探索&発注
        new_ords = stg.think(trade_num, to, order_mgr.get(status=OrderStatus.ACTIVE),
                             long_pos_size=pos_mgr.sum_size(side=Side.BUY),
                             short_pos_size=pos_mgr.sum_size(side=Side.SELL),
                             mid_price=b.iloc[0]['mid_price'] if not b.empty else None,
                             best_ask_price=b.iloc[0]['best_ask_price'] if not b.empty else None,
                             best_bid_price=b.iloc[0]['best_bid_price'] if not b.empty else None)  # type: List[Order]
        order_mgr.add_orders(new_ords)

        # 時間枠ごとに状況を記録する
        orders_each_trade.append(new_ords)
        his_mgr.add_history(time=to,
                            buy_pos_size=pos_mgr.sum_size(side=Side.BUY),
                            sell_pos_size=pos_mgr.sum_size(side=Side.SELL),
                            buy_volume=round(float(new_exec[new_exec['side'] == 'BUY']['size'].sum()), 8),
                            sell_volume=round(float(new_exec[new_exec['side'] == 'SELL']['size'].sum()) * -1, 8),
                            ltp=ltp,
                            realized_pnl=trd_mgr.sum_pnl(), unrealized_pnl=pos_mgr.sum_unrealized_pnl(ltp),
                            exec_recv_delay=new_exec['delay'].mean(),
                            order_delay=sum([d(o.delay_sec) for o in new_ords]) / len(new_ords) if new_ords else 0.0,
                            market_volume=new_exec['size'].sum())

        # 時間を進める
        _from = to
        to = _from + timedelta(seconds=conf.timeframe_sec)
        trade_num += 1
        logger.debug(f"End trading.\n")

        # 約定履歴データがこれ以上存在しない場合は、ループを終了する
        if to > exec.tail(1).index:
            break

    res = {'datetime': datetime.now().strftime(DATETIME_F),
           'duration': time.time() - st,
           'exchange': conf.exchange,
           'data_from': exec.head(1).index.to_pydatetime()[0].strftime(DATETIME_F),
           'data_to': to.strftime(DATETIME_F),
           'data_length': len(exec),
           'timeframe_sec': conf.timeframe_sec,
           'num_of_timeframes': trade_num}
    res.update(his_mgr.get())
    res.update(order_mgr.stats())
    res.update(trd_mgr.stats())
    return res


def raise_err_if_not_exists(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found. [{path}]")


if __name__ == '__main__':
    try:
        st = time.time()
        pd.options.display.width = 300
        logging.config.fileConfig('./logging.conf', disable_existing_loggers=False)
        logger = getLogger(__name__)

        order_mgr = OrderManager()  # type: OrderManager
        pos_mgr = PositionManager()  # type: PositionManager
        his_mgr = HistoryManager()  # type: HistoryManager
        trd_mgr = TradeManager()  # type: TradeManager
        orders_each_trade = []  # type: List[Orders]

        parser = ArgumentParser()
        parser.add_argument('-c', '--conf', required=False, action='store', dest='conf', help='')
        parser.add_argument('-f', '--file', required=False, action='store', dest='file', help='')
        parser.add_argument('-b', '--boards', required=False, action='store', dest='boards', help='')
        args = parser.parse_args()

        raise_err_if_not_exists(args.conf)
        raise_err_if_not_exists(args.file)
        raise_err_if_not_exists(args.boards)

        conf = config.Config(args.conf)  # type: config.Config
        user_settings = {}  # type: dict
        for k, v in conf.user.items():
            user_settings.update({str(k): v})

        # バックテスト実行
        result = run()

        # バックテスト結果を出力
        # bktrepo.print_orders(order_mgr.get())
        # bktrepo.print_executions(orders)
        # bktrepo.print_positions(positions)
        bktrepo.print_graph(orders_each_trade, result, conf.report_dst_dir)
        print(f"Time: {time.time() - st}")

    except Exception as e:
        logger.exception(e)
