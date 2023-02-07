from utils.bottom_trade_tools import get_52060_values


class BottomCommonCondition:
    def __init__(self):
        self.ema5 = 0.0
        self.ema20 = 0.0
        self.ema60 = 0.0
        self.macd = 0.0
        self.close = 0.0
        self.condition_time = None

    def setVByKline(self, kline):
        e5, e20, e60, macd, close, _, k_time =\
                get_52060_values(kline)
        self.ema5 = e5
        self.ema20 = e20
        self.ema60 = e60
        self.macd = macd
        self.close = close
        self.condition_time = k_time


class BottomConditionInfo:
    def __init__(self, custom_symbol, symbol):
        self.custom_symbol = custom_symbol
        self.symbol = symbol
        self.last_price = 0.0
        self.pos = 0
        self.balance = 0
        self.open_pos_scale = 0
        self.contract_m = 0
        self.day_condition = None
        self.hours_condition = None
        self.minutes_condition = None

    def setDayCByKline(self, kline):
        self.day_condition = BottomCommonCondition()
        self.day_condition.setVByKline(kline)
        self.datetime = self.day_condition.condition_time

    def set_day_condition(self, bcc: BottomCommonCondition):
        self.day_condition = bcc
        self.datetime = self.day_condition.condition_time

    def setHoursByKline(self, kline):
        self.hours_condition = BottomCommonCondition()
        self.hours_condition.setVByKline(kline)

    def set_hours_condition(self, bcc: BottomCommonCondition):
        self.hours_condition = bcc

    def setMinutesCByKline(self, kline):
        self.minutes_condition = BottomCommonCondition()
        self.minutes_condition.setVByKline(kline)

    def set_minutes_condition(self, bcc: BottomCommonCondition):
        self.minutes_condition = bcc
