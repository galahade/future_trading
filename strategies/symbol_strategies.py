from abc import abstractmethod
from dao.odm.future_trade import MainJointSymbolStatus
import dao.trade.trade_service as service
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
        self.mjs_status = self._get_MJSymbol_status()
        self.config.setCustomSymbol(self.mjs_status.custom_symbol)
        self.current_trade_strategy: TradeStrategy =\
            self._create_trade_strategy(self.mjs_status.current_symbol)
        self.next_trade_strategy: TradeStrategy =\
            self._create_trade_strategy(self.mjs_status.next_symbol)

    def swith_symbol(self):
        '''换月

        换月流程：
            1. 对当前交易策略进行平仓操作
            2. 将下个交易策略设置为当前交易策略
            3. 从配置文件中获得再下一个交易合约，并创建对应的交易策略, 并设置为下个交易策略
        '''
        next_symbol = get_next_symbol(
            self.config.quote.underlying_symbol,
            self.config.f_info.main_symbols)
        order = self.current_trade_strategy.closeout(2, '换月')
        status = self.current_trade_strategy.ts
        self.current_trade_strategy = self.next_trade_strategy
        status = service.switch_symbol(
            status, next_symbol, self.config.quote.datetime, order)
        self.next_trade_strategy = self._create_trade_strategy(status.symbol)

    @abstractmethod
    def _create_trade_strategy(self, symbol: str) -> TradeStrategy:
        pass

    @abstractmethod
    def _get_name(self) -> str:
        pass

    def _get_MJSymbol_status(self) -> MainJointSymbolStatus:
        return service.get_MJStatus(
            self.config.f_info.symbol, self.config.quote.underlying_symbol,
            get_next_symbol(
                self.config.quote.underlying_symbol,
                self.config.f_info.main_symbols), 1,
            self.config.quote.datetime, self._get_name())


class MJMainStrategy(MJStrategy):
    '''主连主策略基类

    该类的子类包括两类：主连做多主策略和主连做空主策略
    '''
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
    def _get_name(self) -> str:
        return 'bottom'


class MJMainLongStrategy(MJMainStrategy):

    def _create_trade_strategy(self, symbol: str) -> TradeStrategy:
        return MainLongTradeStrategy(self.config, symbol)


class MJMainShortStrategy(MJMainStrategy):

    def _create_trade_strategy(self, symbol: str) -> TradeStrategy:
        return MainShortTradeStrategy(self.config, symbol)

    def execute_before_trade(self):
        pass

    def execute_trade(self):
        pass

    def execute_after_trade(self):
        pass


class MJBottomLongStrategy(MJBottomStrategy):

    def _create_trade_strategy(self, symbol: str) -> TradeStrategy:
        return BottomLongTradeStrategy(self.config, symbol)

    def execute_before_trade(self):
        pass

    def execute_trade(self):
        pass

    def execute_after_trade(self):
        pass


class MJBottomShortStrategy(MJBottomStrategy):

    def _create_trade_strategy(self, symbol: str) -> TradeStrategy:
        return BottomShortTradeStrategy(self.config, symbol)

    def execute_before_trade(self):
        pass

    def execute_trade(self):
        pass

    def execute_after_trade(self):
        pass
