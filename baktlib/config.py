# coding: utf-8

from configparser import ConfigParser


class Config(object):

    def __init__(self, config_file_path: str):
        conf = ConfigParser()
        conf.read(config_file_path)  # type: list

        section = 'default'

        self.exchange = str(conf[section]['exchange'])  # type: str
        """取引所"""

        self.timeframe_sec = int(conf[section]['timeframe_sec'])  # type: int
        """"""

        self.num_of_trade = int(conf[section]['num_of_trade'])  # type: int
        """トレードの施行回数（時間枠の数）"""

        self.report_dst_dir = str(conf[section]['report_dst_dir'])  # type: str

        self.strategy = str(conf[section]['strategy'])  # type: str

        self.user = conf['user']

        # self.order_expire_sec = int(conf[section]['order_expire_sec'])  # type: int
        # self.delay_order_creation_sec = float(conf[section]['delay_order_creation_sec'])  # type: float
        # self.pos_limit_size = float(conf[section]['pos_limit_size'])  # type: float
