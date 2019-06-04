# coding: utf-8

from decimal import Decimal
from enum import Enum

ORDER_STATUS_ACTIVE = 'ACTIVE'  # type: str
"""注文ステータス：アクティブ"""

ORDER_STATUS_CANCELED = 'CANCELED'  # type: str
"""注文ステータス：キャンセル済み"""

ORDER_STATUS_PARTIAL = 'PARTIAL'  # type: str
"""注文ステータス：一部約定済み"""

ORDER_STATUS_COMPLETED = 'COMPLETED'  # type: str
"""注文ステータス：約定済み"""

ORDER_TYPE_LIMIT = 'LIMIT'  # type: str
"""注文種別：指値"""

ORDER_TYPE_MARKET = 'MARKET'  # type: str
"""注文種別：成行"""

SIDE_BUY = 'BUY'  # type: str
"""売買種別：買い"""

SIDE_SELL = 'SELL'  # type: str
"""売買種別：売り"""

DATETIME_F = '%Y-%m-%d %H:%M:%S'
""""""

ZERO = Decimal('0')  # type: Decimal
"""ゼロ"""

DTYPES_EXEC = {'exec_date': 'str',
               'id': 'int',
               'side': 'str',
               'price': 'float',
               'size': 'float',
               'buy_child_order_acceptance_id': 'str',
               'sell_child_order_acceptance_id': 'str',
               'delay': 'float'}

DTYPES_BOARDS = {'time': 'str',
                 'mid_price': 'int',
                 'best_ask_price': 'int',
                 'best_ask_size': 'float',
                 'best_bid_price': 'int',
                 'best_bid_size': 'float',
                 'spread': 'int'}


class Side(Enum):
    """
    注文、約定のside（買いor売り）
    """

    BUY = 'BUY'
    """買い"""

    SELL = 'SELL'
    """売り"""


class OrderStatus(Enum):
    """
    注文ステータス
    """

    ACTIVE = 'ACTIVE'  # type: str
    """注文ステータス：アクティブ"""

    CANCELED = 'CANCELED'  # type: str
    """注文ステータス：キャンセル済み"""

    PARTIAL = 'PARTIAL'  # type: str
    """注文ステータス：一部約定済み"""

    COMPLETED = 'COMPLETED'  # type: str
    """注文ステータス：約定済み"""


class OrderType(Enum):
    """
    注文種別
    """

    LIMIT = 'LIMIT'  # type: str
    """指値"""

    MARKET = 'MARKET'  # type: str
    """成行"""
