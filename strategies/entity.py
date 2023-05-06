from tqsdk import TqApi
from dao.odm.future_config import FutureConfigInfo


class StrategyConfig:
    '''策略配置'''
    def __init__(self, api: TqApi, f_info: FutureConfigInfo, direction: int,
                 is_backtest: bool = False):
        self.api = api
        self.quote = api.get_quote(f_info.symbol)
        self.f_info = f_info
        self.direction = direction
        self.is_backtest = is_backtest

    def get_mj_symbol(self):
        return self.f_info.symbol

    def getSwitchDaysList(self):
        return self.f_info.switch_days

    def getLongTradeConfig(self):
        return self.f_info.long_config

    def getShortTradeConfig(self):
        return self.f_info.short_config

    def getMainSymbolList(self):
        return self.f_info.main_symbols

    def getKlineLength(self):
        return 100

    def getDailyK_Duration(self):
        return 24 * 60 * 60

    def get3hK_Duration(self):
        return 3 * 60 * 60

    def get30mK_Duration(self):
        return 60 * 30
