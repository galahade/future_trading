import strategies.tools as tools
from dao.odm.future_trade import BottomOpenCondition
from strategies.trade_strategies.bts.bottom_trade_strategy import (
    BottomTradeStrategy,
)
from strategies.trade_strategies.trade_strategies import LongTradeStrategy


class BottomLongTradeStrategy(BottomTradeStrategy, LongTradeStrategy):
    """摸底做多交易策略"""

    def _is_dk_macd_matched(self) -> bool:
        kline = self._get_last_dkline()
        if tools.has_set_k_attr(kline, "l_macd_matched"):
            return bool(kline.l_matched)
        return False

    def _match_dk_condition(self) -> bool:
        logger = self.logger
        kline = self._get_last_dkline()
        result = False
        s = self.ts.symbol
        (
            e5,
            e20,
            e60,
            macd,
            close,
            trade_time,
            k_date_str_short,
            _,
        ) = self._get_indicators(kline)
        log_str = (
            "{} {} <摸底做多> 满足日线 K线时间:{} ema5:{} ema20:{} "
            "ema60:{} 收盘:{} MACD:{}"
        )
        if e5 < e20 < e60 and close > e5:
            if macd > 0:
                self._macd_matched = True
            content = log_str.format(
                trade_time, s, k_date_str_short, e5, e20, e60, close, macd
            )
            logger.debug(content)
            result = True
            if self.ts.open_condition is None:
                self.ts.open_condition = BottomOpenCondition()
            self._set_open_condition(
                kline, self.ts.open_condition.daily_condition  # type: ignore
            )
        return result

    def _match_3h_condition(self) -> bool:
        logger = self.logger
        kline = self._get_last_last_3h_kline()
        result = False
        _, _, _, macd, _, trade_time, _, k_date_str = self._get_indicators(
            kline
        )
        log_str = "{} {} <摸底做多> 满足3小时 K线时间:{} MACD:{}"
        if macd > 0:
            content = log_str.format(
                trade_time, self.ts.symbol, k_date_str, macd
            )
            logger.debug(content)
            result = True
            self._set_open_condition(
                kline, self.ts.open_condition.hourly_condition
            )
        return result

    def _match_30m_condition(self) -> bool:
        logger = self.logger
        kline = self._get_last_last_30m_kline()
        result = False
        (
            e5,
            e20,
            e60,
            macd,
            close,
            trade_time,
            k_date_str_short,
            _,
        ) = self._get_indicators(kline)
        log_str = (
            "{} {} <摸底做多> 满足30分钟条件 K线时间:{} ema5:{} ema20:{} "
            "ema60:{} 收盘:{} MACD:{}"
        )
        if close > e60 and e5 > e60:
            if self._is_within_distance(kline, self._macd_matched):
                result = True
                content = log_str.format(
                    trade_time,
                    self.ts.symbol,
                    k_date_str_short,
                    e5,
                    e20,
                    e60,
                    close,
                    macd,
                )
                logger.debug(content)
                self._set_open_condition(
                    kline, self.ts.open_condition.minute_30_condition
                )
        return result

    def _set_sold_prices(self, trade_price: float):
        s_c = self.ts.sold_condition
        s_c.stop_loss_price = self._calc_price(
            trade_price,
            self.config.f_info.short_config.stop_loss_scale,
            False,
        )
        s_c.tp_started_point = self._calc_price(
            trade_price,
            self.config.f_info.short_config.profit_start_scale,
            True,
        )
        self.logger.info(
            f"{self._get_trade_date_str()} {self.symbol} "
            f"<做空>开仓价:{trade_price}"
            f"止损设为:{s_c.stop_loss_price}"
            f"止盈起始价为:{s_c.tp_started_point}"
        )
