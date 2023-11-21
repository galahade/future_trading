from strategies.trade_strategies.bts.bottom_trade_strategy import (
    BottomTradeStrategy,
)
from strategies.trade_strategies.trade_strategies import ShortTradeStrategy


class BottomShortTradeStrategy(BottomTradeStrategy, ShortTradeStrategy):
    def _match_dk_condition(self) -> bool:
        """做空日线条件检测, 合约交易日必须大于等于60天"""
        logger = self.logger
        result = False
        kline = self.last_daily_kline
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
            "{} {} <摸底做空> 满足日线 K线时间:{} ema5:{} ema20:{} "
            "ema60:{} 收盘:{} MACD:{}"
        )
        if e5 > e20 > e60 and close < e5:
            if macd < 0:
                self._macd_matched = True
            content = log_str.format(
                trade_time,
                self.symbol,
                k_date_str_short,
                e5,
                e20,
                e60,
                close,
                macd,
            )
            logger.debug(content)
            result = True
            try:
                self._set_open_condition(
                    kline, self.open_condition.daily_condition
                )
            except ValueError as e:
                self.logger.debug(f"{self.symbol}-{self.direction}:设置开仓条件出现错误")
                raise e
        return result

    def _match_3h_condition(self) -> bool:
        logger = self.logger
        kline = self._get_last_last_3h_kline()
        result = False
        _, _, _, macd, _, trade_time, _, k_date_str = self._get_indicators(
            kline
        )
        log_str = "{} {} <摸底做空> 满足3小时 K线时间:{} MACD:{}"
        if macd < 0:
            content = log_str.format(trade_time, self.symbol, k_date_str, macd)
            logger.debug(content)
            result = True
            self._set_open_condition(
                kline, self.open_condition.hourly_condition
            )
        return result

    def _match_30m_condition(self) -> bool:
        logger = self.logger
        kline = self._get_last_last_30m_kline()
        result = False
        s = self.symbol
        (
            e5,
            e20,
            e60,
            macd,
            close,
            trade_time,
            _,
            k_date_str,
        ) = self._get_indicators(kline)
        log_str = (
            "{} {} <摸底做空> 满足30分钟条件 K线时间:{} ema5:{} ema20:{} "
            "ema60:{} 收盘:{} MACD:{}"
        )
        if close < e60 and e5 < e60:
            if self._is_within_distance(kline, self._macd_matched):
                result = True
                content = log_str.format(
                    trade_time, s, k_date_str, e5, e20, e60, close, macd
                )
                logger.debug(content)
                self._set_open_condition(
                    kline, self.open_condition.minute_30_condition
                )
        return result

    def _set_close_prices(self, trade_price: float):
        s_c = self.close_condition
        s_c.stop_loss_price = self._calc_price(
            trade_price,
            self.config.f_info.short_config.stop_loss_scale,
            True,
        )
        s_c.tp_started_point = self._calc_price(
            trade_price,
            self.config.f_info.short_config.profit_start_scale,
            False,
        )
        self.logger.info(
            f"{self.trade_date_str} {self.symbol} "
            f"<做空>开仓价:{trade_price}"
            f"止损设为:{s_c.stop_loss_price}"
            f"止盈起始价为:{s_c.tp_started_point}"
        )
