from datetime import datetime
from typing import List, Dict, Any

import numpy as np

from baktlib.constants import *
from baktlib.calc import sub
from baktlib.models import Order, Position, Execution


def d(num) -> Decimal:
    return Decimal(str(num))


class OrderManager(object):

    @staticmethod
    def sum_size(orders) -> float:
        return float(sum([Decimal(str(o.size)) for o in orders]))

    def __init__(self):
        self.__orders = []  # type: List[Order]

    def get(self, side: Side = None, _type: OrderType = None, status: OrderStatus = None) -> List[Order]:
        ret = self.__orders

        if side:
            if side not in [Side.BUY, Side.SELL]:
                raise ValueError()
            ret = [o for o in ret if o.side == side.value]

        if _type:
            if _type not in [OrderType.LIMIT, OrderType.MARKET]:
                raise ValueError()
            ret = [o for o in ret if o.type == _type.value]

        if status:
            defined_status = [OrderStatus.ACTIVE,
                              OrderStatus.CANCELED,
                              OrderStatus.COMPLETED,
                              OrderStatus.PARTIAL]
            if not status or status not in defined_status:
                raise ValueError()
            ret = [o for o in ret if o.status == status.value]

        return ret

    def len(self, side: str = None, _type: str = None, status: OrderStatus = None) -> int:
        return len(self.get(side, _type, status))

    def size(self, side: Side = None, _type: OrderType = None, status: OrderStatus = None) -> int:
        return __class__.sum_size(self.get(side, _type, status))

    def add_order(self, order: Order) -> None:
        if not order or not isinstance(order, Order):
            raise ValueError('Order must not be null.')
        self.__orders.append(order)

    def add_orders(self, orders: List[Order]) -> None:
        if orders:
            self.__orders.extend(orders)

    def get_active_orders(self, now: datetime) -> List[Order]:
        """有効な注文の一覧を返します。
        作成された注文が有効であるかの判断には、ステータスに加え、板乗りまでの時間も考慮します。
        作成されてから一定時間（delay_order_creation_sec）が経過した注文を有効と判断します。
        :param now: 現在日時
        :return: 有効な注文の一覧
        """
        if not now:
            raise ValueError
        return [o for o in self.get(status=OrderStatus.ACTIVE) if (now - o.created_at).total_seconds() >= o.delay_sec]
        # return [o for o in self.__orders if o.status == 'ACTIVE' and (now - o.created_at).total_seconds() >= o.delay_sec]

    # def get_orders_by_side(self, side: str) -> List[Order]:
    #     if not side or side not in [SIDE_BUY, SIDE_SELL]:
    #         raise ValueError()
    #     return [o for o in self.__orders if o.side == side]

    # def get_orders_by_type(self, _type: str) -> List[Order]:
    #     if not _type or _type not in [ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET]:
    #         raise ValueError()
    #     return [o for o in self.__orders if o.type == _type]

    # def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
    #     defined_status = [OrderStatus.ACTIVE,
    #                       OrderStatus.CANCELED,
    #                       OrderStatus.COMPLETED,
    #                       OrderStatus.PARTIAL]
    #     if not status or status not in defined_status:
    #         raise ValueError()
    #     return [o for o in self.__orders if o.status == status.value]

    def get_total_size(self) -> float:
        return float(sum([Decimal(o.size) for o in self.__orders]))

    def get_executions(self) -> List[Execution]:
        executions = []  # type: List[Execution]
        for o in self.__orders:
            executions.extend(o.executions)
        return executions

    def sum_exec_size(self) -> float:
        return round(float(sum([Decimal(str(o.size - o.open_size)) for o in self.__orders])), 8)

    def cancel(self, to: datetime):

        # 有効な注文を抽出する
        active_orders = self.get_active_orders(to)  # type: List[Order]

        # 注文作成後の経過時間が有効期限を過ぎていれば該当の注文をキャンセルする
        for o in active_orders:
            if o.expire_sec and (to - o.created_at).total_seconds() > o.expire_sec:
                o.cancel()

    def stats(self) -> Dict[str, Any]:

        num = self.len()
        size = self.get_total_size()
        exec_size = self.sum_exec_size()

        return {
            'num_of_orders': num,
            'num_of_buy_orders': len(self.get(side=Side.BUY)),
            'num_of_sel_orders': len(self.get(side=Side.SELL)),
            'num_of_lmt_orders': len(self.get(_type=OrderType.LIMIT)),
            'num_of_mkt_orders': len(self.get(_type=OrderType.MARKET)),
            'num_of_completed_orders': len(self.get(status=OrderStatus.COMPLETED)),
            'num_of_canceled_orders': len(self.get(status=OrderStatus.CANCELED)),
            'num_of_active_orders': len(self.get(status=OrderStatus.ACTIVE)),
            'num_of_exec': len(self.get_executions()),
            'size_of_orders': size,
            'size_of_limit_orders': self.size(_type=OrderType.LIMIT),
            'size_of_market_orders': self.size(_type=OrderType.MARKET),
            'size_of_exec': exec_size,
            'avg_order_size': round(size / num, 8) if num else 0,
            'exec_rate': round(exec_size / size, 2) if size else 0,
        }


class PositionManager(object):

    def __init__(self):
        self.__positions = []  # type: List[Position]
        self.__id = 0  # type: int

    def get(self) -> List[Position]:
        return self.__positions

    def add_position(self, exec_date, o: Order, amount: float, fee_rate: float):
        if not exec_date or not o.side or not o.price or not amount or not o.id:
            raise ValueError
        self.__id = self.__id + 1
        p = Position(self.__id, exec_date, o.side, o.price, amount, fee_rate, o.id)
        self.__positions.append(p)

    def delete_positions(self, i: int) -> None:
        del self.__positions[i]

    def len(self) -> int:
        return len(self.__positions)

    def sum_size(self, side: str) -> float:
        oa = [Decimal(str(p.open_amount)) for p in self.filter(side=side)]
        return round(float(sum(oa)), 8) if oa else 0.0

    def sum_unrealized_pnl(self, ltp: float) -> int:
        """未実現損益の金額を返します。
        最終取引価格（ltp）に基づいて、保有中のポジションの未実現損益（含み損益）を計算して返します。
        :param ltp: 最終取引価格
        :return: 未実現損益
        """
        if not self.__positions:
            return 0
        if self.__positions[0].side == SIDE_BUY:
            pnl = [(d(ltp) - d(p.open_price)) * d(p.open_amount) for p in self.__positions]
        elif self.__positions[0].side == SIDE_SELL:
            pnl = [(d(p.open_price) - d(ltp)) * d(p.open_amount) for p in self.__positions]
        return round(float(sum(pnl)))

    def filter(self, side: Side = None) -> List[Position]:
        ret = self.__positions
        if side:
            if side not in [Side.BUY, Side.SELL]:
                raise ValueError()
            ret = [p for p in ret if p.side == side.value]
        return ret

    def get_open_size(self) -> float:
        if self.__positions:
            return round(float(sum([Decimal(str(p.open_amount)) for p in self.__positions])), 8)
        return 0.0

    def contract(self, can_exec_size_by_order, buy_ok: bool, sell_ok: bool, exec_date, exec_price, o, trades):

        for i, p in enumerate(self.__positions):

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
                self.delete_positions(i)
                # del positions[i]

            # 発注量を消化しきったらpositionsのループをbreakして次の注文の処理へ
            if can_exec_size_by_order == 0:
                break


class TradeManager(object):

    def __init__(self):
        self.__positions = []  # type: List[Position]

    def get(self) -> List[Position]:
        return self.__positions

    def add_trade(self, position: Position) -> None:
        if not position:
            raise ValueError
        self.__positions.append(position)

    def sum_pnl(self) -> float:
        return round(float(sum([p.pnl for p in self.__positions])), 8)

    def sum_pnl_positive(self):
        return round(float(sum([p.pnl for p in self.__positions if p.pnl > 0])), 8)

    def sum_pnl_negative(self):
        return round(float(sum([p.pnl for p in self.__positions if p.pnl < 0])), 8)

    def sum_size(self) -> float:
        return round(float(sum([p.size for p in self.__positions])), 8)

    def stats(self) -> Dict[str, Any]:
        import pandas as pd

        # 注文IDと損益の表を作成
        t = pd.DataFrame(data={'open_order_id': [p.open_order_id for p in self.__positions],
                               'pnl': [p.pnl for p in self.__positions]})  # type: pd.DataFrame

        # 注文IDごとの損益
        t_pnl_by_order = t.groupby('open_order_id').sum()

        # 勝敗はポジション単位ではなく、注文単位で計測する
        num_of_trades = len(t_pnl_by_order)
        num_of_win = len(t_pnl_by_order[t_pnl_by_order['pnl'] > 0])
        num_of_lose = len(t_pnl_by_order[t_pnl_by_order['pnl'] < 0])
        num_of_even = len(t_pnl_by_order[t_pnl_by_order['pnl'] == 0])
        win_rate = num_of_win / num_of_trades if num_of_trades else 0
        profit = self.sum_pnl_positive()
        loss = abs(self.sum_pnl_negative())
        avg_profit = profit / num_of_win if num_of_win else 0
        avg_loss = loss / (num_of_lose + num_of_even) if num_of_lose + num_of_even else 0

        return {'num_of_trades': num_of_trades,
                'num_of_win': num_of_win,
                'num_of_lose': num_of_lose,
                'num_of_even': num_of_even,
                'win_rate': win_rate,
                'profit': profit,
                'loss': loss,
                'expected_value': avg_profit * win_rate - avg_loss * (1 - win_rate),
                'total_pnl': profit - loss,
                'pf': round(profit / loss, 2) if loss else 0.0}


class HistoryManager(object):

    def __init__(self):
        self.__time = []  # type: datetime
        self.__buy_pos_sizes = []  # type: BuyPositionSizes
        self.__sell_pos_sizes = []  # type: SellPositionSizes
        self.__realized_pnl = []  # type: RealizedPnl
        self.__unrealized_pnl = []  # type: UnrealizedPnl
        self.__ltp = []  # type: LTP
        self.__buy_volumes = []
        self.__sell_volumes = []
        self.__times = []
        self.__orders = []  # type: List[Orders]
        self.__exec_recv_delay = []
        self.__order_delay = []
        self.__market_volumes = []

    def add_history(self,
                    time: datetime,
                    buy_pos_size: float,
                    sell_pos_size: float,
                    buy_volume: float,
                    sell_volume: float,
                    ltp: float,
                    realized_pnl: float,
                    unrealized_pnl: float,
                    orders=None,
                    exec_recv_delay: float = None,
                    order_delay: float = None,
                    market_volume: float = None):
        self.__time.append(time)
        self.__buy_pos_sizes.append(buy_pos_size)
        self.__sell_pos_sizes.append(sell_pos_size)
        self.__buy_volumes.append(buy_volume)
        self.__sell_volumes.append(sell_volume)
        self.__ltp.append(ltp)
        self.__realized_pnl.append(realized_pnl)
        self.__unrealized_pnl.append(unrealized_pnl)
        # self.__timies.append(time)
        # self.__orders.append(orders)
        self.__exec_recv_delay.append(exec_recv_delay)
        self.__order_delay.append(order_delay)
        self.__market_volumes.append(market_volume)

    def get(self) -> Dict[str, List[float]]:
        return {'time': self.__time,
                'buy_pos_size': self.__buy_pos_sizes,
                'sell_pos_size': self.__sell_pos_sizes,
                'market_buy_size': self.__buy_volumes,
                'market_sell_size': self.__sell_volumes,
                'last_prices': self.__ltp,
                'realized_gain': np.array(self.__realized_pnl),
                'unrealized_gain': np.array(self.__unrealized_pnl),
                'exec_recv_delay_sec': self.__exec_recv_delay,
                'order_delay_sec': self.__order_delay,
                'volume': round(float(sum([Decimal(str(v)) for v in self.__market_volumes])), 8)}
