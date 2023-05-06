from abc import abstractmethod
from tqsdk import TqApi
from dao.odm.future_trade import MainJointSymbolStatus
import dao.trade.trade_service as service
from strategies.cyclical_strategies import CyclicalStrategy
from strategies.entity import StrategyConfig
from strategies.trade_strategies.bottom_trade_strategies import (
    BottomLongTradeStrategy, BottomShortTradeStrategy
)
from strategies.trade_strategies.main_trade_strategies import (
    MainLongTradeStrategy,
    MainShortTradeStrategy
)
from strategies.trade_strategies.trade_strategies import (
    Strategy,
    TradeStrategy
)
from utils.common_tools import get_next_symbol


class MJStrategy(Strategy):
    '''主连合约策略基类

    该类的子类包括两类：主连主策略和主连摸底策略
    '''
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.current_trade_strategy: TradeStrategy = None
        self.next_trade_strategy: TradeStrategy = None
        self.mjs_status: MainJointSymbolStatus = None
        self._get_MJSymbol_status()

    @abstractmethod
    def _get_MJSymbol_status(self):
        pass

    @abstractmethod
    def _get_name(self) -> str:
        pass

    def swith_symbol(self, symbol: str):
        '''切换合约'''
        order = self.current_trade_strategy.closeout(2, '换月')
        service.switch_symbol(
            self.mjs_status, symbol, self.config.quote.datetime, order)


class MJMainStrategy(MJStrategy):
    '''主连主策略基类

    该类的子类包括两类：主连做多主策略和主连做空主策略
    '''
    def __init__(self, s_config: StrategyConfig):
        super().__init__(s_config)
        self._get_MJSymbol_status()

    def _get_MJSymbol_status(self):
        self.mjs_status = service.get_main_sts(
            self.config.symbol, self.quote.underlying_symbol,
            get_next_symbol(
                self.quote.underlying_symbol, self.config.main_symbols
            ), 1, self.quote.datetime, self._get_name())

    def _get_name(self) -> str:
        return 'main'

    def execute_before_trade(self):
        self.current_trade_strategy.execute_before_trade()
        self.next_trade_strategy.execute_before_trade()

    def execute_trade(self):
        self.current_trade_strategy.execute_trade()
        self.next_trade_strategy.execute_trade()

    def execute_after_trade(self):
        self.current_trade_strategy.execute_after_trade()
        self.next_trade_strategy.execute_after_trade()


class MJBottomStrategy(MJStrategy):
    '''主连摸底策略基类

    该类的子类包括两类：主连做多摸底策略和主连做空摸底策略
    '''
    def __init__(self, s_config: StrategyConfig):
        super().__init__(s_config)
        self._get_MJSymbol_status()

    def _get_MJSymbol_status(self):
        self.mjs_status = service.get_bottom_sts(
            self.config.symbol, self.quote.underlying_symbol,
            get_next_symbol(
                self.quote.underlying_symbol, self.config.main_symbols
            ), 1, self.quote.datetime, self._get_name())

    def _get_name(self) -> str:
        return 'bottom'


class MJMainLongStrategy(MJMainStrategy):
    def __init__(self, s_config: StrategyConfig):
        super().__init__(s_config)
        self.current_trade_strategy = \
            MainLongTradeStrategy(s_config, self.mjs_status.current_ts)
        self.next_trade_strategy = \
            MainLongTradeStrategy(s_config, self.mjs_status.next_ts)


class MJMainShortStrategy(MJMainStrategy):
    def __init__(self, s_config: StrategyConfig):
        super().__init__(s_config)
        self.current_trade_strategy = \
            MainShortTradeStrategy(s_config, self.mjs_status.current_ts)
        self.next_trade_strategy = \
            MainShortTradeStrategy(s_config, self.mjs_status.next_ts)

    def execute_before_trade(self):
        pass

    def execute_trade(self):
        pass

    def execute_after_trade(self):
        pass


class MJBottomLongStrategy(MJBottomStrategy):
    def __init__(self, s_config: StrategyConfig):
        super().__init__(s_config)
        self.current_trade_strategy = \
            BottomLongTradeStrategy(s_config, self.mjs_status.current_ts)
        self.next_trade_strategy = \
            BottomLongTradeStrategy(s_config, self.mjs_status.next_ts)

    def execute_before_trade(self):
        pass

    def execute_trade(self):
        pass

    def execute_after_trade(self):
        pass


class MJBottomShortStrategy(MJBottomStrategy):
    def __init__(self, s_config: StrategyConfig):
        super().__init__(s_config)
        self.current_trade_strategy = \
            BottomShortTradeStrategy(s_config, self.mjs_status.current_ts)
        self.next_trade_strategy = \
            BottomShortTradeStrategy(s_config, self.mjs_status.next_ts)

    def execute_before_trade(self):
        pass

    def execute_trade(self):
        pass

    def execute_after_trade(self):
        pass


class SymbolsStrategies(Strategy):
    '''主连合约策略基类

    其子类目前有两个：主连主策略和主连摸底策略
    每种策略都有多个方向的策略，如主连主策略有多头策略和空头策略
    根据传入的方向参数，创建对应的策略：如 1 代表多头策略，0 代表空头策略，2 代表多空策略
    '''

    def __init__(self, s_config: StrategyConfig, direction: int):
        super().__init__(s_config)
        self.direction = direction
        self.long_strategy = None
        self.short_strategy = None
        self._create_strategies()
        self.cycle_strategy = CyclicalStrategy(
            self.quote.expire_rest_days, s_config.switch_days, self)

    @abstractmethod
    def get_direction_strategy(self, direction: int):
        pass

    def _create_strategies(self):
        if self.direction in [1, 2]:
            self.long_strategy = self.get_direction_strategy(1)
        if self.direction in [0, 2]:
            self.short_strategy = self.get_direction_strategy(0)

    @staticmethod
    def get_strategy_by_id(
            api: TqApi, s_config: StrategyConfig, direction: int, sid: int):
        """工厂方法，根据 sid 创建对应的多合约策略

        Args:
            api (TqApi): 天勤 api 实例
            s_config (StrategyConfig): 策略配置信息
            direction (int): 策略方向，1 代表多头策略，0 代表空头策略，2 代表多空策略
            sid (int): 策略类型：1 代表主策略，2 代表摸底策略

        Raises:
            ValueError: 目前支持的 sid 只有 1 和 2，其他值会抛出异常,为不支持的策略类型

        Returns:
            SymbolsStrategies: 返回该类的子类实例，如 SymbolsMainStrategies
        """
        if sid == 1:
            return SymbolsMainStrategies(s_config, direction)
        elif sid == 2:
            return SymbolsBottomStrategies(s_config, direction)
        else:
            raise ValueError('sid must be 1 or 2')

    def execute_before_trade(self):
        if self.long_strategy is not None:
            self.long_strategy.execute_before_trade()
        if self.short_strategy is not None:
            self.short_strategy.execute_before_trade()

    def execute_trade(self):
        if self.long_strategy is not None:
            self.long_strategy.execute_trade()
        if self.short_strategy is not None:
            self.short_strategy.execute_trade()

    def execute_after_trade(self):
        if self.long_strategy is not None:
            self.long_strategy.execute_after_trade()
        if self.short_strategy is not None:
            self.short_strategy.execute_after_trade()


class SymbolsMainStrategies(SymbolsStrategies):
    '''主策略，根据交易方向可以包含做多和做空策略'''

    def __init__(self, s_config: StrategyConfig, direction: int):
        super().__init__(s_config, direction)
        self.sid = 1

    def get_direction_strategy(self, direction: int):
        if direction == 1:
            return MJMainLongStrategy(self.config)
        elif direction == 0:
            return MJMainShortStrategy(self.config)


class SymbolsBottomStrategies(SymbolsStrategies):
    def __init__(self, s_config: StrategyConfig, direction: int):
        super().__init__(s_config, direction)
        self.sid = 2

    def get_direction_strategy(self, direction: int):
        if direction == 1:
            return MJBottomLongStrategy(self.config)
        if direction == 0:
            return MJBottomShortStrategy(self.config)
