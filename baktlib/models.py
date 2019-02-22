# coding: utf-8

from datetime import datetime
from decimal import Decimal
from logging import getLogger

from baktlib.constants import *
from baktlib.helpers.calc import d

logger = getLogger(__name__)


class Order(object):
    """注文情報"""

    def __init__(self, id: int, created_at: datetime, side: str, _type: str, size: float,
                 price: float = 0, delay_sec: float = 0.0, expire_sec: int = 0) -> None:

        if not id:
            raise ValueError(f"id is required.")
        if not created_at:
            raise ValueError(f"created_at is required.")
        if side not in [SIDE_BUY, SIDE_SELL]:
            raise ValueError(f"Illegal value [side='{side}']")
        if _type not in [ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET]:
            raise ValueError(f"Illegal value [_type='{_type}']")
        if size <= 0:
            raise ValueError(f"The size must be a number greater than 0. [size='{size}']")

        self.id = id

        self.created_at = created_at
        """注文作成日時"""

        self.side = side
        """"注文種別（BUY or SELL）"""

        self.type = _type

        self.price = price

        self.size = size

        self.open_size = size

        self.delay_sec = delay_sec  # type: float
        """この注文が約定可能になるまでの遅延時間（秒）"""

        self.expire_sec = expire_sec if _type == ORDER_TYPE_LIMIT else -1  # type: int
        """この注文の有効時間（秒）
        有効時間を指定することによって、取引所APIが持つ注文の有効期限設定機能や、発注後一定時間が経過した注文をキャンセルする戦略をテストすることが可能です。
        0は無期限を表します。
        """

        self.status = ORDER_STATUS_ACTIVE
        self.executions = []  # type: List
        logger.debug(f"Created {self}")

    def cancel(self) -> None:
        """注文をキャンセルします。"""
        self.status = ORDER_STATUS_CANCELED
        logger.debug(f"Order was canceled. [{self}]")

    def contract(self, exec_date: datetime, exec_price: float, exec_size: float) -> None:
        """指定したサイズで注文を約定します。
        :param exec_date: 約定日時
        :param exec_price: 約定価格
        :param exec_size: 約定サイズ
        """

        # 約定価格と注文価格に不整合が発生していないかチェック
        if self.type == ORDER_TYPE_LIMIT:
            m = f"Contract price is inappropriate. [side={self.side}, order_price={self.price}, exec_price={exec_price}]"
            if self.side == SIDE_BUY:
                assert exec_price <= self.price, m
            elif self.side == SIDE_SELL:
                assert exec_price >= self.price, m

        # 約定サイズが注文サイズを超えていないかチェック
        assert exec_size <= self.open_size, \
            f"Size is too large. [{self.id}, exec_size={exec_size}, open_size={self.open_size}]"

        self.open_size = round(float(d(self.open_size) - d(exec_size)), 8)
        if self.open_size == 0:
            self.status = ORDER_STATUS_COMPLETED

        # 約定履歴を作成
        self.executions.append(Execution(order_id=self.id,
                                         created_at=exec_date,
                                         side=self.side,
                                         price=exec_price,
                                         size=exec_size,))
        logger.debug(f"Order was {'full' if self.open_size == 0 else 'partial'} contracted. [{self}]")

    def is_active(self) -> bool:
        """この注文が有効であるかどうかを返します。
        注文が、全約定済み、またはキャンセル済みでなければ、有効と判断します。
        :return: 注文が有効な場合True、そうでない場合False。
        """
        return self.status == ORDER_STATUS_ACTIVE

    def __str__(self):
        return f"Order[id={self.id}, created_at={self.created_at}, side={self.side}, type={self.type}," \
            f" size={self.size}, open_size={self.open_size}, price={self.price}, status={self.status}]" \
            f" delay_sec={self.delay_sec}, expire_sec={self.expire_sec}"


class Execution(object):

    def __init__(self, order_id: int, created_at: datetime, side: str,
                 size: float, price: float, delay: float = 0):
        self.order_id = order_id  # type: int
        self.created_at = created_at  # type: datetime
        self.side = side  # type: str
        self.size = size  # type: float
        self.price = price  # type: float
        self.delay = delay  # type: float
        logger.debug(f"Created {self}")

    def __str__(self):
        return f"Execution[order_id={self.order_id}, created_at={self.created_at}, side={self.side}" \
            f", size={self.size}, price={self.price}, delay={self.delay}]"


class Position(object):

    def __init__(self, id: int, opened_at: datetime, side: str, open_price: float, amount: float, fee_rate: float,
                 open_order_id: int):

        self.id = id
        self.open_order_id = open_order_id
        self.opened_at = opened_at
        self.side = side
        self.amount = amount
        self.open_price = open_price
        self.open_amount = amount
        self.open_fee = 0
        self.closed_at = None
        self.close_price = None
        self.close_fee = 0
        self.pnl = 0
        logger.debug(f"Created {self}")

    def close(self, exec_date: datetime, exec_price: float, exec_size: float) -> float:

        logger.debug(f"Start to close position. {self}")

        # クローズ済みの分を含むポジションの全体量
        amount = d(self.amount)  # type: Decimal

        # ポジションの現在のオープン量
        open_amount = d(self.open_amount)  # type: Decimal

        # クローズ価格
        close_price = d(exec_price)  # type: Decimal

        # クローズが既に発生している場合は、過去の約定済み金額を算出
        if self.close_price:
            closed_amount = amount - open_amount
            past = d(self.close_price) * closed_amount  # type: Decimal
        else:
            past = d(0)

        # TODO bitFlyer
        # 損益計算
        if self.side == SIDE_BUY:
            current_pnl = round((close_price - d(self.open_price)) * d(exec_size))
        elif self.side == SIDE_SELL:
            current_pnl = round((d(self.open_price) - close_price) * d(exec_size))
        else:
            raise SystemError(f"Illegal value [side='{self.side}'")

        # 過去の損益と今回クローズした分の損益の合計を計算
        self.pnl = round(float(d(self.pnl) + current_pnl))

        # 約定総額 = 今回約定金額＋約定済み金額
        self.close_price = round(float((past + close_price * open_amount) / amount))
        self.close_fee = 0  # TODO feeに対応させる
        self.closed_at = exec_date
        self.open_amount = round(float(open_amount - d(exec_size)), 8)

        logger.debug(f"Position was closed({'partial' if self.open_amount else 'full'}). {self}")

    def __str__(self):
        return f"Position[id={self.id}, side={self.side}, amount={self.amount}, open_order_id={self.open_order_id}, " \
            f"opened_at={self.opened_at}, open_amount={self.open_amount}, open_price={self.open_price}, " \
            f"open_fee={self.open_fee}, closed_at={self.closed_at}, close_price={self.close_price}, close_fee={self.close_fee}]"
