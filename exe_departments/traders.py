from abc import abstractmethod
import stat
from typing import List
from tqsdk import TqApi
from dao.odm.future_config import FutureConfigInfo
from strategies.cyclical_strategies import CyclicalStrategy
from strategies.entity import StrategyConfig
from strategies.symbol_strategies import (
    MJBottomLongStrategy, MJBottomShortStrategy, MJMainLongStrategy, MJMainShortStrategy, SymbolsStrategies, MJStrategy
)
from utils.common import LoggerGetter


class Trader():
    '''分为激活的交易员和观察交易员。激活的交易员参与实盘交易，观察交易员进行盘前交易提示。
    每个期货品种对应一个交易人，交易人可以使用多种交易策略. 
    记录交易品种相关信息，包括：主连合约，主力合约，quote，个级别k线等，接受盯盘人发出的信号，并根据信号调用相关策略，
    同时记录交易策略运行结果。当符合开仓/平仓条件后调用开仓/平仓工具进行交易
    '''
    logger = LoggerGetter()

    def __init__(
            self, api: TqApi, future_info: FutureConfigInfo,
            strategy_ids: list(int), direction: int = 2, is_bt: bool = False):
        self.is_active = future_info.is_active
        self._api = api
        # self.quote = api.get_quote(future_info.symbol)
        self.future_info = future_info
        self._direction = direction
        self.strategy_traders = []  # type: List[StrategyTrader]
        self._init_s_traders(strategy_ids, is_bt)

    def _init_s_traders(self, strategy_ids: list(int), is_bt):
        '''初始化策略交易人, 每种交易策略对应一个策略交易人'''
        for sid in strategy_ids:
            self.strategy_traders.append(StrategyTrader.get_strader_by_sid(
                self._api, self.future_info, self._direction, sid, is_bt))

    def execute_trade(self):
        '''执行交易操作'''
        if self.is_active:
            for s_trader in self.strategy_traders:
                s_trader.execute_trade()

    def execute_before_trade(self):
        '''交易前的准备工作,比如在实盘交易中的摸底策略需要将符合开仓条件的合约记录在数据库中
        '''
        for s_trader in self.strategy_traders:
            s_trader.execute_before_trade()


class StrategyTrader:
    def __init__(self, s_config: StrategyConfig,):
        self.s_config = s_config
        self.long_mjs = None  # type: MJStrategy
        self.short_mjs = None  # type: MJStrategy
        self._create_MJ_strategy()
        self.cycle_strategy = CyclicalStrategy(
            self)
        
    def _create_MJ_strategy(self):
        '''根据交易方向类型创建主连策略
 
        交易方向类型决定了策略交易者所拥有的主连方向策略：
        1. 多头策略交易者拥有多头主连策略
        0. 空头策略交易者拥有空头主连策略
        2. 多空策略交易者拥有多头和空头主连策略
        '''
        if self.s_config.direction in [1, 2]:
            self.long_mjs = self._get_mjs_by_direction(1)
        if self.s_config.direction in [0, 2]:
            self.short_mjs = self._get_mjs_by_direction(0)

    @staticmethod
    def get_strader_by_sid(
            api: TqApi, future_info: FutureConfigInfo,
            direction: int, sid: int, is_bt: bool):
        """工厂方法，根据 sid 创建相应的策略交易者

        Args:
            api (TqApi): 天勤 api 实例
            future_info: (FutureConfigInfo): 主连合约配置信息
            direction (int): 策略方向，1 代表多头策略，0 代表空头策略，2 代表多空策略
            sid (int): 策略类型：1 代表主策略，2 代表摸底策略
            is_bt (bool): 是否是回测

        Raises:
            ValueError: 目前支持的 sid 只有 1 和 2，其他值会抛出异常,为不支持的策略类型

        Returns:
            SymbolsStrategies: 返回该类的子类实例，如 SymbolsMainStrategies
        """
        s_config = StrategyConfig(api, future_info, direction, is_bt)
        if sid == 1:
            return MainStrategyTrader(s_config)
        if sid == 2:
            return BottomStrategyTrader(s_config)
        raise ValueError('sid must be 1 or 2')

    @abstractmethod
    def _get_mjs_by_direction(self, direction: int):
        """根据交易方向获取该类型交易人对应的主连策略

        Args:
            direction (int): 交易方向，1 代表多头策略，0 代表空头策略，2 代表多空策略
        """

    def execute_before_trade(self):
        if self.long_mjs is not None:
            self.long_mjs.execute_before_trade()
        if self.short_mjs is not None:
            self.short_mjs.execute_before_trade()

    def execute_trade(self):
        if self.long_mjs is not None:
            self.long_mjs.execute_trade()
        if self.short_mjs is not None:
            self.short_mjs.execute_trade()

    def execute_after_trade(self):
        if self.long_mjs is not None:
            self.long_mjs.execute_after_trade()
        if self.short_mjs is not None:
            self.short_mjs.execute_after_trade()


class MainStrategyTrader(StrategyTrader):
    '''主力合约交易员'''

    def __init__(self, s_config: StrategyConfig):
        super().__init__(s_config)
        self._init_trader()

    def _init_trader(self):
        '''初始化交易员'''
        self._trader = SymbolsStrategies.get_strategy_by_id(
            self._api, self.future_info, self._direction, 0)

    def execute_trade(self):
        '''执行交易操作'''
        self._trader.execute_trade()

    def execute_before_trade(self):
        '''交易前的准备工作,比如在实盘交易中的摸底策略需要将符合开仓条件的合约记录在数据库中
        '''
        self._trader.execute_before_trade()

    def _get_mjs_by_direction(self, direction: int):
        """根据交易方向获取该类型交易人对应的主连策略

        Args:
            direction (int): 交易方向，1 代表多头策略，0 代表空头策略，2 代表多空策略
        """
        if direction == 1:
            return MJMainLongStrategy(self.s_config)
        if direction == 0:
            return MJMainShortStrategy(self.s_config)
        raise ValueError('direction must be 1 or 0')


class BottomStrategyTrader(StrategyTrader):
    '''摸底策略交易员'''

    def __init__(self, s_config: StrategyConfig,):
        super().__init__(s_config)
        self._init_trader()

    def _init_trader(self):
        '''初始化交易员'''
        self._trader = SymbolsStrategies.get_strategy_by_id(
            self._api, self.future_info, self._direction, 1)

    def execute_trade(self):
        '''执行交易操作'''
        self._trader.execute_trade()

    def execute_before_trade(self):
        '''交易前的准备工作,比如在实盘交易中的摸底策略需要将符合开仓条件的合约记录在数据库中
        '''
        self._trader.execute_before_trade()

    def _get_mjs_by_direction(self, direction: int):
        """根据交易方向获取该类型交易人对应的主连策略

        Args:
            direction (int): 交易方向，1 代表多头策略，0 代表空头策略，2 代表多空策略
        """
        if direction == 1:
            return MJBottomLongStrategy(self.s_config)
        if direction == 0:
            return MJBottomShortStrategy(self.s_config)
        raise ValueError('direction must be 1 or 0')
