from datetime import datetime
from decimal import Decimal

from constants import *


class Order(object):

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

    def cancel(self) -> None:
        self.status = ORDER_STATUS_CANCELED

    def contract(self, exec_size) -> None:
        if exec_size > self.open_size:
            raise ValueError(f"Size is too large. [exec_size={exec_size}, open_size={self.open_size}]")
        self.open_size = round(float(Decimal(self.open_size) - Decimal(exec_size)), 8)
        if self.open_size == 0:
            self.status = ORDER_STATUS_COMPLETED

    def is_active(self) -> bool:
        return self.status == ORDER_STATUS_ACTIVE

    def __str__(self):
        return f"Order[id={self.id}, {self.created_at}, side={self.side}, type={self.type}," \
            f" size={self.size}, price={self.price}, status={self.status}]"
