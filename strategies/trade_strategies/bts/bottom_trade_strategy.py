from abc import abstractmethod
from datetime import datetime, timedelta

from tqsdk import tafunc
from tqsdk.objs import Order

import dao.trade.trade_service as service
import strategies.tools as tools
import utils.common_tools as c_tools
import utils.tqsdk_tools as tq_tools
from dao.odm.future_trade import (
    BottomIndicatorValues,
    BottomOpenCondition,
    BottomTradeStatus,
)
from strategies.entity import StrategyConfig
from strategies.trade_strategies.trade_strategies import TradeStrategy
from utils.common_tools import LoggerGetter


class BottomTradeStrategy(TradeStrategy):
    logger = LoggerGetter()

    def __init__(self, config: StrategyConfig, symbol: str):
        super().__init__(config, symbol)
        self.tip = service.get_last_bottom_tip_by_symbol(
            self.symbol, self.direction
        )
        self._macd_matched = False

    def fill_indicators_by_type(self, k_type: int):
        """根据K线类型填充指标 1:全部K线 2:日线 3:3小时线 4:30分钟线"""
        if k_type == 1:
            self.fill_indicators_by_type(2)
            self.fill_indicators_by_type(3)
            self.fill_indicators_by_type(4)
        elif k_type == 2:
            tools.fill_bottom_indicators(self._d_klines)
        elif k_type == 3:
            tools.fill_bottom_indicators(self._3h_klines)
        elif k_type == 4:
            tools.fill_bottom_indicators(self._30m_klines)

    def _can_get_tips(self) -> bool:
        """是否符合摸底提示条件

        当满足提示条件时，返回 True
        """
        d_kline = self.last_daily_kline
        tip = service.get_lbt_by_symbol_date(
            self.symbol,
            self.direction,
            tafunc.time_to_datetime(d_kline.datetime),
        )
        logger = self.logger
        if tip is None:
            if self._match_dk_condition():
                if self._match_3h_condition():
                    if self._match_30m_condition():
                        logger.info("<摸底策略>符合生成开仓提示条件".ljust(100, "-"))
                        return True
        return False

    def _can_open_pos(self) -> bool:
        """是否符合开仓条件

        当该合约没有开仓时，判断是否符合开仓条件，符合则开仓
        如有开仓则不作开仓操作。
        """
        logger = self.logger
        if not self.is_trading:
            if self._need_trade():
                logger.info("<摸底策略>符合开仓条件, 准备开仓".ljust(100, "-"))
                return True
        return False

    def _need_trade(self) -> bool:
        """判断是否有摸底提示
        如果有提示，并且将需要交易的状态设为真时返回真"""
        if self.tip is not None:
            return self.tip.need_trade
        return False

    def _is_within_distance(self, last_matched_kline, is_macd_matched) -> bool:
        """30分钟线需要判断与最近符合条件的30分钟线的距离是否在5根以内"""
        logger = self.logger
        trade_date_str = self.trade_date_str
        log_str = (
            "{} {} 前一交易日最后30分钟线时间:{}, 满足条件的30分"
            "钟线时间{}, 满足条件前一根30分钟线ema5:{}, ema60:{}, close:{}."
        )
        m30_klines = self._30m_klines
        m30_klines = m30_klines[
            m30_klines.datetime < last_matched_kline.datetime
        ].iloc[::-1]
        wanted_kline = m30_klines.iloc[-10]
        distance = 5
        is_match = False
        for i, t_kline in m30_klines.iterrows():
            e5, _, e60, _, close, _, _, _ = self._get_indicators(t_kline)
            if close <= e60 or e5 <= e60:
                wanted_kline = self._30m_klines.iloc[i + 1]
                content = log_str.format(
                    trade_date_str,
                    self.symbol,
                    tq_tools.get_date_str(last_matched_kline.datetime),
                    tq_tools.get_date_str(wanted_kline.datetime),
                    e5,
                    e60,
                    close,
                )
                logger.debug(content)
                break
        if is_macd_matched:
            last_date = tafunc.time_to_datetime(last_matched_kline.datetime)
            last_date = datetime(
                last_date.year, last_date.month, last_date.day, 21
            )
            lastdate_timestamp = tafunc.time_to_ns_timestamp(
                last_date + timedelta(days=-1)
            )
            if lastdate_timestamp <= wanted_kline.datetime:
                logger.debug(
                    "前一交易日MACD>0 "
                    f"开始时间:{tq_tools.get_date_str(lastdate_timestamp)} "
                    f"满足条件30分钟线时间:"
                    f"{tq_tools.get_date_str(wanted_kline.datetime)} "
                    "符合在同一交易日的条件"
                )
                is_match = True
        else:
            if last_matched_kline.id - wanted_kline.id < distance:
                logger.debug(
                    f"上一交易日30分钟线id:{last_matched_kline.id},"
                    f"满足条件的30分钟线id:{wanted_kline.id}"
                    "满足距离小于5的条件"
                )
                is_match = True
        return is_match

    def _try_stop_loss(self):
        """摸底策略暂时只用作提示，不涉及止损"""
        pass

    def _get_last_dk_date(self) -> datetime:
        d_kline = self.last_daily_kline
        dk_time = c_tools.get_china_date_from_dt(
            tafunc.time_to_datetime(d_kline.datetime)
        )
        return dk_time

    def _get_last_last_3h_kline(self):
        last_trade_date = self._get_last_dk_date()
        h3_klines = self._3h_klines
        lastday_last_3hk_time = last_trade_date.replace(hour=12)
        l_timestamp = tafunc.time_to_ns_timestamp(lastday_last_3hk_time)
        return h3_klines[h3_klines.datetime <= l_timestamp].iloc[-1]

    def _get_last_last_30m_kline(self):
        last_trade_date = self._get_last_dk_date()
        m30_klines = self._30m_klines
        lastday_lasth3k_time = last_trade_date.replace(hour=14, minute=30)
        l_timestamp = tafunc.time_to_ns_timestamp(lastday_lasth3k_time)
        return m30_klines[m30_klines.datetime <= l_timestamp].iloc[-1]

    def execute_after_trade(self):
        """摸底策略收盘后执行一次该方法，
        目前天勤返回的数据不支持收盘时进行摸底判断，因为该时段收盘价不是最终收盘价
        故不使用收盘生成摸底策略"""

    def _generate_tips(self):
        if self._can_get_tips():
            log_str = "{} {} {} 符合开仓条件, 开盘后注意关注开仓 " "前一日收盘价:{}, 预计开仓:{} 手"
            dkline = self.last_daily_kline
            pos = self._calc_open_pos(dkline.close)
            content = log_str.format(
                self.trade_date,
                self.symbol,
                self.trade_status.custom_symbol,
                dkline.close,
                pos,
            )
            self.logger.info(content)
            service.store_b_open_volume_tip(
                self.trade_status, self.open_condition, pos
            )

    def _store_open_pos_info(self, order: Order):
        if self.tip is not None:
            service.open_bottom_pos(self.trade_status, order, self.tip)

    def _get_indicators(self, kline) -> tuple:
        ema5 = kline.ema5
        ema20 = kline.ema20
        ema60 = kline.ema60
        macd = kline["MACD.close"]
        close = kline.close
        kline_time_str_short = tq_tools.get_date_str_short(kline.datetime)
        kline_time_str = tq_tools.get_date_str(kline.datetime)
        return (
            ema5,
            ema20,
            ema60,
            macd,
            close,
            self.trade_date,
            kline_time_str_short,
            kline_time_str,
        )

    def _init_trade_status(self, symbol: str) -> BottomTradeStatus:
        """获取交易状态"""
        return service.get_bottom_trade_status(
            self.config.custom_symbol,
            symbol,
            self.direction,
            self.config.quote.datetime,
        )

    def _set_open_condition(self, kline, biv: BottomIndicatorValues):
        """设置开仓条件"""
        (
            biv.ema5,
            biv.ema20,
            biv.ema60,
            biv.macd,
            biv.close,
            _,
            _,
            _,
        ) = self._get_indicators(kline)
        biv.kline_time = tq_tools.get_datetime_from_ns(kline.datetime)

    def _set_close_condition(self):
        """目前摸底策略未实现平仓策略，留作日后补充"""
        pass

    def _try_take_profit(self):
        """摸底策略暂时只用作提示，不提供止盈策略"""
        pass

    def _get_strategy_name(self) -> int:
        return "摸底策略"

    @property
    def open_condition(self) -> BottomOpenCondition:
        if self.is_trading:
            return self.trade_status.open_pos_info.tip.open_condition
        if self._open_condition is None:
            self._open_condition = BottomOpenCondition(
                daily_condition=BottomIndicatorValues(),
                hourly_condition=BottomIndicatorValues(),
                minute_30_condition=BottomIndicatorValues(),
            )
        return self._open_condition

    @property
    def trade_status(self) -> BottomTradeStatus:
        return self._ts

    @abstractmethod
    def _match_dk_condition(self) -> bool:
        pass

    @abstractmethod
    def _match_3h_condition(self) -> bool:
        pass

    @abstractmethod
    def _match_30m_condition(self) -> bool:
        pass
