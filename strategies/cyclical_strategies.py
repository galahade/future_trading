from exe_departments.traders import StrategyTrader
from strategies.symbol_strategies import MJStrategy


class CyclicalStrategy:
    '''根据策略交易者提供的它所管理的多空方向的主连合约策略的相关信息，进行换月操作

    策略交易者所提供的主连合约策略是根据合约配置生成的，可以包括多空任一方向，也可以包括多空双方向。
    当某个方向的主连合约策略到了换月时间时，会调用该主连合约策略的换月方法，进行换月操作。
    '''
    def __init__(self, s_trader: StrategyTrader):
        self.switch_days = s_trader.s_config.f_info.switch_days
        self.trade_switch_day = s_trader.s_config.f_info.switch_days[0]
        self.no_trade_switch_day = s_trader.s_config.f_info.switch_days[1]
        self.s_trader = s_trader
        self.erd = s_trader.s_config.quote.expire_rest_days

    def _is_time_to_switch(self, mjstrategy: MJStrategy) -> bool:
        '''判断是否到了切换时间'''
        result = False
        c_ts = mjstrategy.current_trade_strategy.ts
        if c_ts.trade_status == 1:
            if self.erd <= self.trade_switch_day:
                result = True
        elif self.erd < self.no_trade_switch_day:
            result = True
        return result

    def _switch_symbol(self, mjs: MJStrategy):
        '''切换合约'''
        if mjs is not None:
            if self._is_time_to_switch(mjs):
                mjs.swith_symbol()

    def execute(self):
        '''执行交易操作'''
        self._switch_symbol(self.s_trader.long_mjs)
        self._switch_symbol(self.s_trader.short_mjs)
