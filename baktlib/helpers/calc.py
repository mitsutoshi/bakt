# coding: utf-8

from decimal import Decimal


def d(f: float) -> Decimal:
    """数値をDecimal型に変換して返します。
    :param f: 数値
    :return: Decimal(str(f))
    """
    return Decimal(str(f))


def add(a, b) -> float:
    da = d(a) if type(a) is not Decimal else a
    db = d(b) if type(b) is not Decimal else b
    return round(float(da + db), 8)


def sub(a, b) -> float:
    da = d(a) if type(a) is not Decimal else a
    db = d(b) if type(b) is not Decimal else b
    return round(float(da - db), 8)


def multi(a, b) -> float:
    da = d(a) if type(a) is not Decimal else a
    db = d(b) if type(b) is not Decimal else b
    return round(float(da * db), 8)
