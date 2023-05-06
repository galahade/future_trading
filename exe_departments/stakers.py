from abc import ABC, abstractmethod
from typing import List
from tqsdk import TqApi
from exe_departments.traders import Trader
from strategies.trade_strategies.trade_strategies import TradeStrategy
from utils.common import LoggerGetter
from utils.config_utils import (get_future_configs)
import dao.config_service as c_service


class Staker(ABC):
    logger = LoggerGetter()
    '''盯盘人，负责盯盘，当盯盘品种价格等参数发生改变时向交易人发送信号'''

    def __init__(self, api: TqApi, trade_strategies: list(TradeStrategy),
                 direction: int):
        self.tqApi = api
        self.t_strategies = trade_strategies
        self.direction = direction
        self.future_configs = None
        self.traders = []  # type: List[Trader]

    def _load_traders(self):
        '''加载交易员'''
        for f_config in self.future_configs:
            for t_strategy in self.t_strategies:
                if t_strategy.future_info.symbol == f_config.symbol:
                    self.traders.append(t_strategy.get_trader(f_config))

    def execute(self):
        '''执行盯盘操作'''
        logger = self.logger
        logger.info(f'交易初始资金为{self.api.get_account().balance}')
        self.api.wait_update()
        logger.info("天勤服务器端已连接成功，开始交易")
        self._prepare_task()
        for trader in self.traders:
            trader.execute_before_trade()
        while True:
            self.api.wait_update()
            for trader in self.traders:
                trader.execute_trade()

    @abstractmethod
    def _prepare_task(self):
        '''交易前的准备工作, 实盘交易打印出参与交易品种的合约信息，回测交易打印出回测的起止时间'''


class RealStaker(Staker):
    '''实盘交易盯盘人'''

    def __init__(self, api: TqApi, trade_strategies: list(TradeStrategy),
                 direction: int):
        super().__init__(api, trade_strategies, direction)
        self.future_configs = c_service.get_future_configs(
            get_future_configs())

    def _prepare_task(self):
        for trader in filter(lambda t: t.is_active, self.traders):
            trader.before_trade()
        self.logger.info('当前参与交易品种为:')
        for trader in filter(lambda t: t.is_active, self.traders):
            self.logger.info(f'{trader._zl_symbol}')


class BTStaker(Staker):
    '''回测交易盯盘人'''

    def __init__(self, api: TqApi, trade_strategies: list(TradeStrategy),
                 direction: int):
        super().__init__(api, trade_strategies, direction)
        self.future_configs = get_future_configs(
            get_future_configs(is_backtest=True))

    def _prepare_task(self):
        '''交易前的准备工作, 实盘交易打印出参与交易品种的合约信息，回测交易打印出回测的起止时间'''
        pass
