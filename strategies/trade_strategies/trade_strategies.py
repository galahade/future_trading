from abc import ABC, abstractmethod
from datetime import datetime
from math import ceil

from pandas import DataFrame
from tqsdk import tafunc
from tqsdk.objs import Order

import dao.trade.trade_service as service
import strategies.tools as tools
import utils.tqsdk_tools as tq_tools
from dao.odm.future_trade import TradeStatus
from strategies.entity import StrategyConfig
from utils.common_tools import LoggerGetter, get_china_date_from_str


class Strategy(ABC):
    """策略基类"""

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
    """交易策略基类"""

    def __init__(self, config: StrategyConfig, symbol: str):
        super().__init__(config)
        self.api = config.api
        self.symbol = symbol
        self._ts = self._init_trade_status(symbol)
        self.quote = self.api.get_quote(symbol)
        self._d_klines = self._init_daily_klines()
        self._3h_klines = self.api.get_kline_serial(
            symbol, self.config.get3hK_Duration()
        )
        self._30m_klines = self.api.get_kline_serial(
            symbol, self.config.get30mK_Duration()
        )
        self._5m_klines = config.api.get_kline_serial(
            symbol, self.config.get5mK_Duration()
        )
        self.fill_indicators_by_type(1)
        self._open_condition = None
        self._close_condition = None

    def __repr__(self):
        debug_str = "{} symbol:{} quote_time:{} ts:{}"
        return debug_str.format(
            self.__class__.__name__,
            self.symbol,
            self.trade_date,
            self.trade_status,
        )

    def execute_before_trade(self):
        """在交易前执行，提供开盘提示等功能
        默认不提供该功能，只在摸底策略中提供盘前提示功能
        """
        self._generate_tips()

    def execute_trade(self):
        """在交易期间，循环执行该方法尝试交易"""
        self._trade_switch_symbol()
        if self.is_trading:
            self._try_close_pos()
        else:
            self._try_open_pos()

    def execute_after_trade(self):
        """在收盘后执行"""

    def closeout(self, c_type: int, c_message: str) -> Order:
        """全部平仓, 可以安全调用，不会重复平仓

        c_type: 0: 止损, 1: 止盈, 2: 换月, 3: 人工平仓
        """
        return self.close_pos(
            self.trade_status.carrying_volume, c_type, c_message
        )

    def open_pos(self, pos: int) -> Order:
        """进行开仓相关操作，并记录开仓信息，输出日志"""
        order = self._trade_pos(pos, "OPEN", self._get_open_direction())
        t_price = self.current_price if order.is_error else order.trade_price
        self._set_open_pos_info(t_price)
        order.trade_price = t_price
        self._store_open_pos_info(order)
        log_str = "{} {} {} 开仓 价格:{} 数量:{}"
        self.logger.info(
            log_str.format(
                tq_tools.get_date_str(self.trade_date),
                self.symbol,
                self.trade_status.custom_symbol,
                t_price,
                pos,
            )
        )
        if not self.config.is_backtest:
            tradeMsg = {
                "custom_symbol": self.trade_status.custom_symbol,
                "symbol": self.symbol,
                "direction": bool(self.direction),
                "pos": pos,
                "price": t_price,
                "t_time": tq_tools.get_date_str(order.insert_date_time),
                "o_or_c": "开仓",
                "message": "开仓",
            }
            tools.sendTradePosMsg(tradeMsg)
        return order

    def close_pos(self, pos: int, c_type: int, c_message: str) -> Order:
        """根据数量进行平仓，并记录平仓信息，输出日志"""
        order = None
        t_price = 0.0
        if self.is_trading:
            order = self._trade_pos(pos, "CLOSE", self._get_close_direction())
            t_price = (
                self.current_price if order.is_error else order.trade_price
            )
            order.trade_price = t_price
            order.close_volume = service.close_ops(
                self.trade_status, c_type, c_message, order
            )
        if not self.config.is_backtest:
            tradeMsg = {
                "custom_symbol": self.trade_status.custom_symbol,
                "symbol": self.symbol,
                "direction": bool(self.direction),
                "pos": pos,
                "price": t_price,
                "t_time": tq_tools.get_date_str(order.insert_date_time),
                "o_or_c": "平仓",
                "message": c_message,
            }
            tools.sendTradePosMsg(tradeMsg)
        return order

    def is_changing(self, k_type: int) -> bool:
        """判断是否有某个周期的K线正在发生改变

        k_type:  1: 3小时线, 2: 30分钟线, 3: 5分钟线
        """
        try:
            if k_type == 1:
                return self.config.api.is_changing(
                    self._3h_klines.iloc[-1], "datetime"
                )
            elif k_type == 2:
                return self.config.api.is_changing(
                    self._30m_klines.iloc[-1], "datetime"
                )
            elif k_type == 3:
                return self.config.api.is_changing(
                    self._5m_klines.iloc[-1], "datetime"
                )
        except Exception as e:
            self.logger.debug(f"{self.symbol} k_type:{k_type} has error {e}")
        return False

    def _init_daily_klines(self) -> DataFrame:
        """获得日线序列, 由于天勤量化实盘中实时获取日线序列会导致错误，故需要特殊处理
        在实盘交易中，由于获取的是日线的拷贝数据。故当日线发生变化时，需要重新获取日线数据。
        """
        if self.config.is_backtest:
            self._d_klines = self.api.get_kline_serial(
                self.symbol,
                self.config.getDailyK_Duration(),
                self.config.getKlineLength(),
            )
        else:
            self._d_klines = self.api.get_kline_serial(
                self.symbol,
                self.config.getDailyK_Duration(),
                self.config.getKlineLength(),
            ).copy()
        return self._d_klines

    def _trade_switch_symbol(self):
        record = service.get_switch_symbol_trade_record(self.trade_status)
        if record is not None:
            ovi = record.current_open_volume_info
            order_c = self.close_pos(ovi.volume, 2, "换月平仓")
            record.close_volume_info = order_c.close_volume
            if record.next_need_open:
                # TO-DO: 当需要换月开仓时，需要确定它的止盈止损条件，
                # 但目前还无法确定，所以暂时不开仓，等待条件确定后在实现开仓逻辑
                record.next_open_status = True
            service.update_switch_symbol_trade_record(record)

    def _trade_pos(self, pos: int, offset: str, trade_direction: str) -> Order:
        """和期货交易所进行期货交易
        先尝试市价下单，如果不支持则将当前价格作为限价尝试下单"""
        logger = self.logger
        try:
            order = self.api.insert_order(
                symbol=self.symbol,
                direction=trade_direction,
                offset=offset,
                volume=pos,
            )
        except Exception:
            logger.debug(f"{self.symbol} 不支持市价下单，尝试使用限价下单")
            if offset == "OPEN":
                limit_price = self._get_open_price()
            else:
                limit_price = self._get_close_price()
            logger.debug(
                f"限价下单: 交易方向:{trade_direction} Offset:{offset} 手数:{pos} 下单价格:{limit_price} 当前价格:{self.quote.last_price}"
            )
            try:
                order = self.api.insert_order(
                    symbol=self.symbol,
                    direction=trade_direction,
                    offset=offset,
                    volume=pos,
                    limit_price=limit_price,
                )
            except Exception as e:
                logger.error(e)
                raise e
        while True:
            self.api.wait_update()
            if order.status == "FINISHED":
                break
        service.store_tq_order(order)
        return order

    def _calc_price(self, o_price: float, scale: float, is_up: bool) -> float:
        """根据给定价格和调整比例和调整方向计算最新价格

        Args:
            o_price (float): 原始价格
            scale (float): 基础调整比例
            is_up (bool): 是否是上浮

        Returns:
            float: 调整后的价格
        """
        if is_up:
            return round(o_price * (1 + self._get_base_scale() * scale), 2)
        else:
            return round(o_price * (1 - self._get_base_scale() * scale), 2)

    def _calc_open_pos(self, price) -> int:
        """计算开仓手数

        根据账户余额与该品种开仓比例计算出交易该品种可用余额，
        可用余额除以开仓价格向上取整，获得可开仓手术"""
        f_info = self.config.f_info
        available = (
            self.api.get_account().available
            * f_info.open_pos_scale
            / f_info.multiple
        )
        self.logger.debug(
            f"交易可用金额:{available} 交易价格:{price} 可用余额:{self.api.get_account().available} 开仓比例:{f_info.open_pos_scale} 合约乘数:{f_info.multiple}"
        )
        pos = ceil(available / price)
        return pos

    def _try_close_pos(self):
        """交易的主要方法，负责判断是否满足平仓条件：当合约有持仓时，尝试止盈或止损
        满足条件后平仓。"""
        if self.is_trading:
            self._try_stop_loss()
            self._try_take_profit()

    def _try_open_pos(self):
        """交易的主要方法，负责判断是否满足开仓条件：当合约无持仓，且满足条件后开仓。"""
        if not self.is_trading:
            if self._can_open_pos():
                try:
                    pos = self._calc_open_pos(self.current_price)
                    self.open_pos(pos)
                except Exception as e:
                    self.logger.debug(f"quote:{self.quote} error: {e}")
                    raise e

    def _set_klines_value(self, klines, k_name, k_key, k_value):
        klines.loc[k_name, k_key] = k_value

    def _set_open_pos_info(self, trade_price: float):
        """设置开仓相关交易信息"""
        self._set_close_condition()
        self._set_close_prices(trade_price)

    @property
    def is_last_5m(self) -> bool:
        """判断是否是最后5分钟"""
        t_time = tafunc.time_to_datetime(self.quote.datetime)
        time_num = int(t_time.time().strftime("%H%M%S"))
        return 150000 > time_num > 145500

    @property
    def trade_status(self) -> TradeStatus:
        return self._ts

    @property
    def is_trading(self) -> bool:
        """判断是否已经有交易存在"""
        return self.trade_status.trade_status == 1

    @property
    def trade_date(self) -> datetime:
        """从天勤的报价对象中获取交易的当前时间"""
        return get_china_date_from_str(self.quote.datetime)

    @property
    def trade_date_str(self) -> str:
        """从天勤的报价对象中获取交易的当前时间"""
        return self.trade_date.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def carrying_volume(self) -> int:
        """获取持仓手数"""
        return self.trade_status.carrying_volume

    @property
    def current_price(self) -> float:
        """获取当前交易所交易价格"""
        return self.quote.last_price

    @property
    def last_daily_kline(self):
        """当该品种处于交易时段，要获取前一根日k线。
        当处于交易结束时段，则获取最后一根日K线"""
        if tq_tools.is_trading_period(self.api, self.quote):
            return self._d_klines.iloc[-2]
        return self._d_klines.iloc[-1]

    @property
    @abstractmethod
    def direction(self) -> int:
        """获取当前交易策略的方向"""

    @abstractmethod
    def _store_open_pos_info(self, order: Order):
        """存储开仓信息"""

    @abstractmethod
    def _init_trade_status(self, symbol: str) -> TradeStatus:
        """初始化交易状态"""

    @abstractmethod
    def _get_open_direction(self) -> str:
        """获取当前交易策略的开仓方向"""

    @abstractmethod
    def _get_close_direction(self) -> str:
        """获取当前交易策略的平仓方向"""

    @abstractmethod
    def _can_open_pos(self) -> bool:
        """判断是否可以开仓"""

    @abstractmethod
    def _try_stop_loss(self):
        """当满足止损条件时，进行止损操作"""

    @abstractmethod
    def _try_take_profit(self) -> None:
        """当满足止盈条件时，进行止盈操作"""

    @abstractmethod
    def _set_close_prices(self, trade_price: float):
        """设置平仓价格"""

    @abstractmethod
    def _get_base_scale(self) -> float:
        """获取当前交易策略的基础开仓比例

        开仓比例为开仓资金占总资金的比例
        """

    @abstractmethod
    def fill_indicators_by_type(self, k_type: int):
        """根据K线类型填充指标 1:全部K线 2:日线 3:3小时线 4:30分钟线 5:5分钟线"""

    @abstractmethod
    def _get_open_price(self) -> float:
        """限价交易品种获取开仓价格"""

    @abstractmethod
    def _get_close_price(self) -> float:
        """限价交易品种获取平仓价格"""

    @abstractmethod
    def _generate_tips(self) -> float:
        """为策略生成提示信息"""

    @abstractmethod
    def _get_strategy_name(self) -> int:
        """获取策略名称"""

    @abstractmethod
    def _set_close_condition(self):
        """设置平仓条件"""


class LongTradeStrategy(TradeStrategy):
    def _get_open_direction(self) -> str:
        return "BUY"

    def _get_close_direction(self) -> str:
        return "SELL"

    @property
    def direction(self) -> int:
        return 1

    def _get_base_scale(self) -> float:
        return self.config.f_info.long_config.base_scale

    def _get_open_price(self) -> float:
        return self.quote.ask_price1

    def _get_close_price(self) -> float:
        return self.quote.bid_price1


class ShortTradeStrategy(TradeStrategy):
    def _get_open_direction(self) -> str:
        return "SELL"

    def _get_close_direction(self) -> str:
        return "BUY"

    @property
    def direction(self) -> int:
        return 0

    def _get_base_scale(self) -> float:
        return self.config.f_info.short_config.base_scale

    def _get_open_price(self) -> float:
        return self.quote.bid_price1

    def _get_close_price(self) -> float:
        return self.quote.ask_price1
