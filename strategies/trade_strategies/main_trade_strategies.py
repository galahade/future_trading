from tqsdk.objs import Order
import dao.trade.trade_service as service
from dao.odm.future_trade import (
    MainTradeStatus)
from strategies.entity import StrategyConfig
from strategies.trade_strategies.trade_strategies import (
    TradeStrategy, LongTradeStrategy, ShortTradeStrategy)
from utils.common_tools import LoggerGetter


class MainTradeStrategy(TradeStrategy):
    logger = LoggerGetter()

    def __init__(
            self, config: StrategyConfig, ts: MainTradeStatus):
        super().__init__(config, ts)

    def execute_before_trade(self):
        pass

    def execute_trade(self):
        pass

    def execute_after_trade(self):
        pass

    def open_pos(self, pos: int) -> Order:
        '''开仓'''
        order = self._trade_pos(pos, 'OPEN')
        service.main_open_pos_operation(self.ts, order)

    def close_pos(self, pos: int, c_type, c_message) -> Order:
        '''平仓'''
        order = self._trade_pos(pos, 'CLOSE')
        service.main_close_pos_operation(
            self.ts, order, c_type, c_message)

    def _can_open_pos(self) -> bool:
        '''判断是否可以开仓'''

    def _try_stop_loss(self):
        '''当满足止损条件时，进行止损操作'''

    def _try_take_profit(self):
        '''当满足止盈条件时，进行止盈操作'''


class MainLongTradeStrategy(MainTradeStrategy, LongTradeStrategy):
    def __init__(self, s_config: StrategyConfig, ts: MainTradeStatus):
        super().__init__(s_config, ts)


class MainShortTradeStrategy(MainTradeStrategy, ShortTradeStrategy):
    def __init__(self, s_config: StrategyConfig, ts: MainTradeStatus):
        super().__init__(s_config, ts)
