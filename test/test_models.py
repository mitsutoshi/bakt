import unittest
from datetime import datetime, timedelta

from baktlib.models import Position


class PositionTest(unittest.TestCase):

    def __assert_position(self, p: Position, id, opened_at, amount, price,
                          open_fee, open_order_id, closed_at, open_amount, close_price, close_fee, pnl):
        self.assertEqual(id, p.id)
        self.assertEqual(opened_at, p.opened_at)
        self.assertEqual(amount, p.amount)
        self.assertEqual(price, p.open_price)
        self.assertEqual(open_fee, p.open_fee)
        self.assertEqual(open_order_id, p.open_order_id)
        self.assertTrue(closed_at, p.closed_at)
        self.assertEqual(open_amount, p.open_amount)
        self.assertEqual(close_price, p.close_price)
        self.assertEqual(close_fee, p.close_fee)
        self.assertEqual(pnl, p.pnl)

    def test_close_one(self):
        id = 1
        opened_at = datetime.now()
        amount = 1.0
        price = 100
        open_order_id = 99
        side = 'BUY'

        p = Position(id=id, opened_at=opened_at, side=side, open_price=price,
                     amount=amount, fee_rate=0, open_order_id=open_order_id)

        closed_at = opened_at + timedelta(minutes=1)
        close_price = price + 1

        p.close(exec_date=closed_at,
                exec_price=close_price,
                exec_size=amount)

        self.__assert_position(p=p, id=id, opened_at=opened_at, amount=amount, price=price,
                               open_fee=0, open_order_id=open_order_id, closed_at=closed_at,
                               open_amount=0, close_price=close_price, close_fee=0, pnl=1)

    def test_close_separate(self):
        id = 1
        opened_at = datetime.now()
        amount = 1.0
        price = 100
        open_order_id = 99
        side = 'BUY'

        p = Position(id=id, opened_at=opened_at, side=side, open_price=price,
                     amount=amount, fee_rate=0, open_order_id=open_order_id)

        closed_at = opened_at + timedelta(minutes=1)
        close_price = price + 10

        p.close(exec_date=closed_at, exec_price=price + 10, exec_size=0.5)

        self.__assert_position(p=p, id=id, opened_at=opened_at, amount=amount, price=price,
                               open_fee=0, open_order_id=open_order_id, closed_at=closed_at,
                               open_amount=0.5, close_price=close_price, close_fee=0, pnl=5)

        p.close(exec_date=closed_at, exec_price=close_price, exec_size=0.5)

        self.__assert_position(p=p, id=id, opened_at=opened_at, amount=amount, price=price,
                               open_fee=0, open_order_id=open_order_id, closed_at=closed_at,
                               open_amount=0, close_price=close_price, close_fee=0, pnl=10)

    def test_close_round_down_pnl(self):
        id = 1
        opened_at = datetime.now()
        amount = 0.01
        price = 1000
        open_order_id = 99
        side = 'BUY'

        p = Position(id=id, opened_at=opened_at, side=side, open_price=price,
                     amount=amount, fee_rate=0, open_order_id=open_order_id)

        closed_at = opened_at + timedelta(minutes=1)
        close_price = price + 50

        p.close(exec_date=closed_at, exec_price=close_price, exec_size=amount)

        self.__assert_position(p=p, id=id, opened_at=opened_at, amount=amount, price=price,
                               open_fee=0, open_order_id=open_order_id, closed_at=closed_at,
                               open_amount=0, close_price=close_price, close_fee=0, pnl=0)

    def test_close_round_up_pnl(self):
        id = 1
        opened_at = datetime.now()
        amount = 0.01
        price = 1000
        open_order_id = 99
        close_price = price + 51
        side = 'BUY'

        p = Position(id=id, opened_at=opened_at, side=side, open_price=price,
                     amount=amount, fee_rate=0, open_order_id=open_order_id)

        closed_at = opened_at + timedelta(minutes=1)
        p.close(exec_date=closed_at, exec_price=close_price, exec_size=amount)

        self.__assert_position(p=p, id=id, opened_at=opened_at, amount=amount, price=price,
                               open_fee=0, open_order_id=open_order_id, closed_at=closed_at,
                               open_amount=0, close_price=close_price, close_fee=0, pnl=1)

    def test_close_separate_round_down_pnl(self):
        id = 1
        opened_at = datetime.now()
        amount = 0.02
        price = 1000
        open_order_id = 99
        side = 'BUY'

        p = Position(id=id, opened_at=opened_at, side=side, open_price=price,
                     amount=amount, fee_rate=0, open_order_id=open_order_id)

        closed_at = opened_at + timedelta(minutes=1)
        close_price = price + 50

        p.close(exec_date=closed_at, exec_price=close_price, exec_size=0.01)

        self.__assert_position(p=p, id=id, opened_at=opened_at, amount=amount, price=price,
                               open_fee=0, open_order_id=open_order_id, closed_at=closed_at,
                               open_amount=0.01, close_price=close_price, close_fee=0, pnl=0)

        p.close(exec_date=closed_at, exec_price=close_price, exec_size=0.01)

        self.__assert_position(p=p, id=id, opened_at=opened_at, amount=amount, price=price,
                               open_fee=0, open_order_id=open_order_id, closed_at=closed_at,
                               open_amount=0.00, close_price=close_price, close_fee=0, pnl=0)

    def test_close_separate_round_up_pnl(self):
        id = 1
        opened_at = datetime.now()
        amount = 0.02
        price = 1000
        open_order_id = 99
        side = 'BUY'

        p = Position(id=id, opened_at=opened_at, side=side, open_price=price,
                     amount=amount, fee_rate=0, open_order_id=open_order_id)

        closed_at = opened_at + timedelta(minutes=1)
        close_price = price + 51
        p.close(exec_date=closed_at, exec_price=close_price, exec_size=0.01)

        self.__assert_position(p=p, id=id, opened_at=opened_at, amount=amount, price=price,
                               open_fee=0, open_order_id=open_order_id, closed_at=closed_at,
                               open_amount=0.01, close_price=close_price, close_fee=0, pnl=1)

        p.close(exec_date=closed_at, exec_price=close_price, exec_size=0.01)

        self.__assert_position(p=p, id=id, opened_at=opened_at, amount=amount, price=price,
                               open_fee=0, open_order_id=open_order_id, closed_at=closed_at,
                               open_amount=0.00, close_price=close_price, close_fee=0, pnl=2)

    def test_close_separate_difference_price(self):
        id = 1
        opened_at = datetime.now()
        amount = 0.02
        price = 1000
        open_order_id = 99
        side = 'BUY'

        p = Position(id=id, opened_at=opened_at, side=side, open_price=price,
                     amount=amount, fee_rate=0, open_order_id=open_order_id)

        closed_at = opened_at + timedelta(minutes=1)
        close_price = price + 50

        p.close(exec_date=closed_at, exec_price=close_price, exec_size=0.01)

        self.__assert_position(p=p, id=id, opened_at=opened_at, amount=amount, price=price,
                               open_fee=0, open_order_id=open_order_id, closed_at=closed_at,
                               open_amount=0.01, close_price=close_price, close_fee=0, pnl=0)

        close_price = price + 100

        p.close(exec_date=closed_at, exec_price=close_price, exec_size=0.01)

        self.__assert_position(p=p, id=id, opened_at=opened_at, amount=amount, price=price,
                               open_fee=0, open_order_id=open_order_id, closed_at=closed_at,
                               open_amount=0, close_price=price + 75, close_fee=0, pnl=1)
