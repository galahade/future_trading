from math import ceil
from abc import ABC, abstractmethod
from tqsdk.objs import Order
import dao.trade.trade_service as service
from dao.odm.future_trade import (TradeStatus)
from strategies.entity import StrategyConfig
from strategies.tools import fill_indicators
from utils.common_tools import LoggerGetter, get_china_date_from_str


class Strategy(ABC):
    '''策略基类'''
    logger = LoggerGetter()

    def __init__(self, config: StrategyConfig):
        self.config = config

    @abstractmethod
    def execute_before_trade(self):
        pass

    @abstractmethod
    def execute_trade(self):
        pass

    @abstractmethod
    def execute_after_trade(self):
        pass


class TradeStrategy(Strategy):
    '''交易策略基类'''

    def __init__(self, config: StrategyConfig,
                 ts: TradeStatus):
        super().__init__(config)
        api = config.api
        self.ts = ts
        self.quote = api.get_quote(ts.symbol)
        self._d_klines = self._get_daily_klines()
        self._3h_klines = api.get_kline_serial(
            ts.symbol, self.config.get3hK_Duration(),
        )
        self._30m_klines = api.get_kline_serial(
            ts.symbol, self.config.get30mK_Duration()
        )

    def execute_trade(self):
        '''在交易期间，循环执行该方法尝试交易,'''
        if self.ts.trade_status == 1:
            self._try_close_pos()
        elif self.ts.trade_status == 0:
            self._try_open_pos()

    def execute_after_trade(self):
        pass

    def closeout(self, c_type: int, c_message: str) -> Order:
        '''平仓, 可以安全调用，不会重复平仓'''
        order = None
        if self.ts.trade_status == 1:
            order = self._trade_pos(self.ts.carrying_volume, 'CLOSE')
            service.close_pos(self.ts, c_type, c_message, order)
        return order

    def _get_daily_klines(self):
        '''获得日线序列, 由于天勤量化实盘中实时获取日线序列会导致错误，故需要特殊处理'''
        if self.config.is_backtest:
            return self.api.get_kline_serial(
                self.ts.symbol, self.config.getDailyK_Duration(),
                self.config.getKlineLength())
        return self.api.get_kline_serial(
            self.ts.symbol, self.config.getDailyK_Duration(),
            self.config.getKlineLength()).copy()

    def _trade_pos(self, pos: int, offset: str) -> Order:
        '''和期货交易所进行期货交易'''
        order = self.api.insert_order(
            symbol=self.sts.symbol,
            direction=self._get_open_direction(),
            offset=offset,
            volume=pos
        )
        while True:
            self.api.wait_update()
            if order.status == "FINISHED":
                break
        return order

    def _fill_indicators_by_type(self, k_type: int):
        '''根据K线类型填充指标
        0: 全部K线
        1: 日线
        2: 3小时线
        3: 30分钟线
        '''
        if k_type == 0:
            self._fill_indicators_by_type(1)
            self._fill_indicators_by_type(2)
            self._fill_indicators_by_type(3)
        elif k_type == 1:
            fill_indicators(self._d_klines)
        elif k_type == 2:
            fill_indicators(self._3h_klines)
        elif k_type == 3:
            fill_indicators(self._30m_klines)

    def _has_dk_changed(self):
        '''当日线生成新K线时返回True'''
        return self.api.is_changing(self._d_klines[-1], 'datetime')

    def _has_3hk_changed(self):
        '''当3小时线生成新K线时返回True'''
        return self.api.is_changing(self._3h_klines[-1], 'datetime')

    def _has_30mk_changed(self):
        '''当30分钟线生成新K线时返回True'''
        return self.api.is_changing(self._30m_klines[-1], 'datetime')

    def _get_trade_date(self):
        '''从天勤的报价对象中获取交易的当前时间'''
        return get_china_date_from_str(self.quote.datetime)

    def _calc_open_pos(self, price) -> int:
        '''计算开仓手数'''
        available = (
            self.api.get_account().balance * self.config.f_info.open_pos_scale)
        pos = ceil(available / price)
        return pos

    def _try_close_pos(self):
        '''交易的主要方法，负责判断是否满足平仓条件：当合约有持仓时，尝试止盈或止损
        满足条件后平仓。'''
        if self.ts.trade_status == 1:
            self._try_stop_loss()
            self._try_take_profit()

    def _try_open_pos(self):
        '''交易的主要方法，负责判断是否满足开仓条件：当合约无持仓时，尝试开仓。
        满足条件后开仓。'''
        if self.ts.trade_status in [0]:
            if self._can_open_pos():
                pos = self._calc_open_pos(self.quote.last_price)
                self.open_pos(pos)

    @abstractmethod
    def _get_open_direction(self) -> str:
        '''获取当前交易策略的开仓方向'''

    @abstractmethod
    def _get_close_direction(self) -> str:
        '''获取当前交易策略的平仓方向'''

    @abstractmethod
    def _can_open_pos(self) -> bool:
        '''判断是否可以开仓'''

    @abstractmethod
    def _try_stop_loss(self):
        '''当满足止损条件时，进行止损操作'''

    @abstractmethod
    def _try_take_profit(self):
        '''当满足止盈条件时，进行止盈操作'''

    @abstractmethod
    def open_pos(self, pos: int) -> Order:
        '''进行开仓相关操作，并记录开仓信息，输出日志'''

    @abstractmethod
    def close_pos(self, pos: int, c_type, c_message) -> Order:
        '''根据平仓条件进行平仓，并记录平仓信息，输出日志'''


class LongTradeStrategy(TradeStrategy):

    def _get_open_direction(self) -> str:
        return 'BUY'

    def _get_close_direction(self) -> str:
        return 'SELL'


class ShortTradeStrategy(TradeStrategy):

    def _get_open_direction(self) -> str:
        return 'SELL'

    def _get_close_direction(self) -> str:
        return 'BUY'
