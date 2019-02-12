# coding: utf-8

from datetime import datetime
from decimal import Decimal
from logging import getLogger

from baktlib.constants import *

logger = getLogger(__name__)


class Order(object):
    """注文情報"""

    def __init__(self, id: int, created_at: datetime, side: str, _type: str, size: float, price: float = 0) -> None:

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
        self.side = side
        self.type = _type
        self.price = price
        self.size = size
        self.open_size = size
        self.status = ORDER_STATUS_ACTIVE
        self.executions = []  # type: List
        logger.debug(f"Order was created. {self}")

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
        assert exec_size <= self.open_size, f"Size is too large. [exec_size={exec_size}, open_size={self.open_size}]"

        self.open_size = round(float(Decimal(self.open_size) - Decimal(exec_size)), 8)
        if self.open_size == 0:
            self.status = ORDER_STATUS_COMPLETED

        # 約定履歴を作成
        self.executions.append(Execution(order_id=self.id,
                                         created_at=exec_date,
                                         side=self.side,
                                         price=exec_price,
                                         size=exec_size))
        logger.debug(f"Order was contracted. [{self}]")

    def is_active(self) -> bool:
        """この注文が有効であるかどうかを返します。
        注文が、全約定済み、またはキャンセル済みでなければ、有効と判断します。
        :return: 注文が有効な場合True、そうでない場合False。
        """
        return self.status == ORDER_STATUS_ACTIVE

    def __str__(self):
        return f"Order[id={self.id}, {self.created_at}, side={self.side}, type={self.type}," \
            f" size={self.size}, open_size={self.open_size}, price={self.price}, status={self.status}]"


class Execution(object):

    def __init__(self, order_id, created_at: datetime, side: str, size: float, price: float):
        self.order_id = order_id
        self.created_at = created_at
        self.side = side
        self.size = size
        self.price = price

    def __str__(self):
        return f"Execution[created_at{self.created_at}, side={self.side}, size={self.size}, price={self.price}]"


class Position(object):

    def __init__(self, id: int, opened_at: datetime, side: str, open_price: float, amount: float, fee_rate: float):
        self.id = id
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
        logger.debug(f"Position was created. {self}")

    def close(self, exec_date: datetime, exec_price: float, exec_size: float) -> float:

        # クローズ済みの分を含むポジションの全体量
        amount = Decimal(self.amount)  # type: Decimal

        # ポジションの現在のオープン量
        open_amount = Decimal(self.open_amount)  # type: Decimal

        # 過去の約定済み金額 = 約定価格 * 約定済みサイズ（amount - open_amount）
        past = Decimal(self.close_price) * (amount - open_amount) if self.close_price else Decimal(0)  # type: Decimal

        # クローズ価格
        close_price = Decimal(exec_price)  # type: Decimal

        # 約定総額 = 今回約定金額＋約定済み金額
        current = close_price * open_amount

        # 損益計算
        if self.side == SIDE_BUY:
            current_pnl = (close_price - Decimal(self.open_price)) * open_amount
        elif self.side == SIDE_SELL:
            current_pnl = (Decimal(self.open_price) - close_price) * open_amount
        else:
            raise SystemError(f"Illegal value [side='{self.side}'")

        # TODO bitFlyerの損益計算に合わせる
        self.pnl = float(Decimal(self.pnl) + current_pnl)
        self.close_price = float((past + current) / amount)

        # TODO feeに対応させる
        self.close_fee = 0
        self.closed_at = exec_date
        self.open_amount = round(float(open_amount - Decimal(exec_size)), 8)

        logger.debug(f"Position was closed({'partial' if self.open_amount else 'full'}). [{self}]")

    def __str__(self):
        return f"Position[id={self.id}, side={self.side}, amount={self.amount}, open_amount={self.open_amount}, " \
            f"opened_at={self.opened_at}, open_price={self.open_price}, open_fee={self.open_fee}, " \
            f"closed_at={self.closed_at}, close_price={self.close_price}, close_fee={self.close_fee}]"
