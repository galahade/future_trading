from abc import abstractmethod
from datetime import datetime, timedelta
from tqsdk import tafunc
from tqsdk.objs import Order
import strategies.tools as tools
import dao.trade.trade_service as service
from dao.odm.future_trade import BottomTradeStatus
from strategies.entity import StrategyConfig
from strategies.trade_strategies.trade_strategies import (
    LongTradeStrategy, ShortTradeStrategy, TradeStrategy)
from utils.common_tools import LoggerGetter
from utils.tqsdk_tools import (
    get_date_str, get_date_str_short)


class BottomTradeStrategy(TradeStrategy):
    logger = LoggerGetter.get_logger()

    def __init__(
            self, config: StrategyConfig, ts: BottomTradeStatus):
        super().__init__(config, ts)

    def open_pos(self, pos: int) -> Order:
        '''进行开仓交易，并将交易结果保存至数据库'''
        order = self._trade_pos(pos, 'OPEN')
        service.bottom_open_pos_operation(self.ts, order)
        log_str = '{} {} {} 开仓. 价格：{} 数量：{}'
        self.logger.info(log_str.format(
            get_date_str(self._get_trade_date()),
            self.ts.symbol, self.ts.custom_symbol, order.trade_price,
            order.volume_orign))

    def close_pos(self, pos: int, c_type, c_message) -> Order:
        '''平仓'''
        order = self._trade_pos(pos, 'CLOSE')
        service.bottom_close_pos_operation(
            self.ts, order, c_type, c_message)

    def _need_before_check(self) -> bool:
        '''该合约是否需要在盘前检查是否符合开仓条件
        回测时不需要，实盘时需要
        '''
        if self.config.is_backtest:
            return False
        return True

    def _can_open_pos(self, is_in=True) -> bool:
        '''是否符合开仓条件
        当该合约没有开仓时，判断是否符合开仓条件，符合则开仓
        如有开仓则不作开仓操作。
        '''
        logger = self.logger
        is_match = False
        if self.ts.trade_status == 0:
            if self._match_dk_condition(is_in):
                if self._match_dk_condition(is_in):
                    if self._match_dk_condition(is_in):
                        is_match = True
                        if is_in:
                            logger.info(
                                '符合开仓条件, 准备开仓'.ljust(100, '-'))
                        else:
                            logger.info(
                                '符合开仓条件, 请注意开仓提示'.ljust(100, '-'))
        return is_match

    def _is_within_distance(self, last_matched_kline, is_macd_matched) -> bool:
        '''30分钟线需要判断与最近符合条件的30分钟线的距离是否在5根以内'''
        logger = self.logger
        trade_date_str = self._get_trade_date().strftime("%Y-%m-%d %H:%M:%S")
        log_str = ('{} {} 前一交易日最后30分钟线时间:{}, 满足条件的30分'
                   '钟线时间{}, 满足条件前一根30分钟线ema5:{}, ema60:{}, close:{}.')
        m30_klines = self._30m_klines
        m30_klines = m30_klines[
            m30_klines.datetime < last_matched_kline.datetime].iloc[::-1]
        wanted_kline = m30_klines.iloc[-10]
        distance = 5
        is_match = False
        for i, t_kline in m30_klines.iterrows():
            e5, _, e60, _, close, _ =\
                self._get_indicators(t_kline)
            if close <= e60 or e5 <= e60:
                wanted_kline = self._30m_klines.iloc[i+1]
                content = log_str.format(
                    trade_date_str, self.ts.symbol,
                    get_date_str(last_matched_kline.datetime),
                    get_date_str(wanted_kline.datetime),
                    e5, e60, close)
                logger.debug(content)
                break
        if is_macd_matched:
            last_date = tafunc.time_to_datetime(last_matched_kline.datetime)
            last_date = datetime(
                last_date.year, last_date.month, last_date.day, 21)
            lastdate_timestamp = tafunc.time_to_ns_timestamp(
                last_date + timedelta(days=-1))
            if lastdate_timestamp <= wanted_kline.datetime:
                logger.debug('前一交易日MACD > 0, '
                             f'开始时间:{get_date_str(lastdate_timestamp)},'
                             f'满足条件30分钟线时间:'
                             f'{get_date_str(wanted_kline.datetime)}'
                             '符合在同一交易日的条件')
                is_match = True
        else:
            if last_matched_kline.id - wanted_kline.id < distance:
                logger.debug(f'上一交易日30分钟线id:{last_matched_kline.id},'
                             f'满足条件的30分钟线id:{wanted_kline.id}'
                             '满足距离小于5的条件')
                is_match = True
        return is_match

    def _try_stop_loss(self):
        pass

    def _try_take_profit(self):
        pass

    @abstractmethod
    def _match_dk_condition(self, is_in=True) -> bool:
        pass

    @abstractmethod
    def _match_3h_condition(self, is_in=True) -> bool:
        pass

    @abstractmethod
    def _match_30m_condition(self, is_in=True) -> bool:
        pass

    def _get_last_kline_in_trade(self, klines, is_in=True):
        if is_in:
            return klines.iloc[-2]
        return klines.iloc[-1]

    def execute_before_trade(self):
        '''每次程序运行执行一次该方法，用来检查当天是否有需要开仓的品种
        目前由于天勤只能在临近开盘时产生下一个交易日K线，而该方法需要
        在收盘后即运行，故其判断开仓使用的日K线有别于开盘后进行交易使用的
        日K线.
        目前逻辑为：当前合约有持仓时，不再盘前提示。否则，如果符合条件则进行提示。
        '''
        if self._need_before_check() and self._can_open_pos(is_in=False):
            log_str = ('{} {} {} 符合开仓条件, 开盘后注意关注开仓 '
                       '前一日收盘价:{}, 预计开仓:{} 手')
            dkline = self._get_last_kline_in_trade(self._d_klines, False)
            pos = self._calc_open_pos(dkline.close)
            ovt = {
                'd_kline': dkline,
                '3h_kline': self._get_last_kline_in_trade(
                    self._3h_klines, False),
                '30m_kline': self._get_last_kline_in_trade(
                    self._30m_klines, False),
                'volume': pos
            }
            content = log_str.format(
                self._get_trade_date(), self.ts.symbol, self.ts.custom_symbol,
                dkline.close, pos
            )
            self.logger.info(content)
            service.store_b_open_volume_tip(self.ts, ovt)

    def _get_indicators(self, kline) -> tuple:
        ema5 = kline.ema5
        ema20 = kline.ema20
        ema60 = kline.ema60
        macd = kline['MACD.close']
        close = kline.close
        trade_time = self._get_trade_date()
        return (ema5, ema20, ema60, macd, close, trade_time)


class BottomLongTradeStrategy(BottomTradeStrategy, LongTradeStrategy):
    '''摸底做多交易策略'''
    logger = LoggerGetter.get_logger()

    def __init__(self, s_config: StrategyConfig, ts: BottomTradeStatus):
        super().__init__(s_config, ts)

    def _match_dk_condition(self, is_in=True) -> bool:
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._d_klines, is_in)
        if tools.has_set_k_attr(kline, 'l_matched'):
            return kline.l_matched
        s = self.ts.symbol
        e5, e20, e60, macd, close, trade_time =\
            self._get_indicators(kline)
        k_date_str = get_date_str_short(kline.datetime)
        log_str = ('{} {} <摸底做多> 满足日线 K线时间:{} ema5:{} ema20:{} '
                   'ema60:{} 收盘:{} MACD:{}')
        if e5 < e20 < e60 and close > e5:
            if macd > 0:
                self._d_klines.loc[kline.name, 'l_macd_matched'] = True
            else:
                self._d_klines.loc[kline.name, 'l_macd_matched'] = False
            content = log_str.format(
                trade_time, s, k_date_str,
                e5, e20, e60, close, macd)
            logger.info(content)
            self._d_klines.loc[kline.name, 'l_matched'] = True
        else:
            self._d_klines.loc[kline.name, 'l_matched'] = False
        return self._d_klines.loc[kline.name, 'l_matched']

    def _match_3h_condition(self, is_in=True) -> bool:
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._3h_klines, is_in)
        if tools.has_set_k_attr(kline, 'l_matched'):
            return kline.l_matched
        _, _, _, macd, _, trade_time = self._get_indicators(kline)
        k_date_str = get_date_str(kline.datetime)
        log_str = '{} {} <摸底做多> 满足3小时 K线时间:{} MACD:{}'
        if macd > 0:
            content = log_str.format(
                trade_time, self.ts.symbol, k_date_str, macd)
            logger.info(content)
            self._3h_klines.loc[kline.name, 'l_matched'] = True
        else:
            self._3h_klines.loc[kline.name, 'l_matched'] = False
        return self._3h_klines.loc[kline.name, 'l_matched']

    def _match_30m_condition(self, is_in=True) -> bool:
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._30m_klines, is_in)
        if tools.has_set_k_attr(kline, 'l_matched'):
            return kline.l_matched
        e5, e20, e60, macd, close, trade_time =\
            self._get_indicators(kline)
        k_date_str = get_date_str(kline.datetime)
        log_str = ('{} {} <摸底做多> 30分钟条件 K线时间:{} ema5:{} ema20:{} '
                   'ema60:{} 收盘:{} MACD:{}')
        if close > e60 and e5 > e60:
            if self._is_within_distance(kline, self._is_long_macd_match):
                self._30m_klines.loc[kline.name, 'l_matched'] = True
                content = log_str.format(
                    trade_time, self.ts.symbol, k_date_str, e5, e20, e60,
                    close, macd)
                logger.info(content)
            else:
                self._30m_klines.loc[kline.name, 'l_matched'] = False
        else:
            self._30m_klines.loc[kline.name, 'l_matched'] = False
        return self._30m_klines.loc[kline.name, 'l_matched']


class BottomShortTradeStrategy(BottomTradeStrategy, ShortTradeStrategy):
    logger = LoggerGetter.get_logger()

    def __init__(self, s_config: StrategyConfig, ts: BottomTradeStatus):
        super().__init__(s_config, ts)

    def _match_dk_condition(self, is_in=True) -> bool:
        '''做空日线条件检测, 合约交易日必须大于等于60天
        '''
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._d_klines, is_in)
        if tools.has_set_k_attr(kline, 's_matched'):
            return kline.s_matched
        s = self.ts.symbol
        e5, e20, e60, macd, close, trade_time =\
            self._get_indicators(kline)
        k_date_str = get_date_str_short(kline.datetime)
        log_str = ('{} {} <摸底做空> 满足日线 K线时间:{} ema5:{} ema20:{} '
                   'ema60:{} 收盘:{} MACD:{}')
        if e5 > e20 > e60 and close < e5:
            if macd < 0:
                self._d_klines.loc[kline.name, 's_macd_matched'] = True
            else:
                self._d_klines.loc[kline.name, 's_macd_matched'] = False
            content = log_str.format(
                trade_time, s, k_date_str, e5, e20, e60, close, macd)
            logger.info(content)
            self._d_klines.loc[kline.name, 's_matched'] = True
        else:
            self._d_klines.loc[kline.name, 's_matched'] = False
        return self._d_klines.loc[kline.name, 's_matched']

    def _match_3h_condition(self, is_in=True) -> bool:
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._3h_klines, is_in)
        if tools.has_set_k_attr(kline, 's_matched'):
            return kline.s_matched
        _, _, _, macd, _, trade_time = self._get_indicators(kline)
        k_date_str = get_date_str(kline.datetime)
        log_str = '{} {} <摸底做空> 满足3小时 K线时间:{} MACD:{}'
        if macd < 0:
            content = log_str.format(
                trade_time, self.ts.symbol, k_date_str, macd)
            logger.info(content)
            self._3h_klines.loc[kline.name, 's_matched'] = True
        else:
            self._3h_klines.loc[kline.name, 's_matched'] = False
        return self._3h_klines.loc[kline.name, 's_matched']

    def _match_30m_condition(self, is_in=True) -> bool:
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._30m_klines, is_in)
        dkline = self._get_last_kline_in_trade(self._d_klines, is_in)
        if tools.has_set_k_attr(kline, 's_matched'):
            return kline.s_matched
        s = self.ts.symbol
        e5, e20, e60, macd, close, trade_time =\
            self._get_indicators(kline)
        k_date_str = get_date_str(kline.datetime)
        log_str = ('{} {} <摸底做空> 满足30分钟条件 K线时间:{} ema5:{} ema20:{} '
                   'ema60:{} 收盘:{} MACD:{}')
        if close < e60 and e5 < e60:
            if self._is_within_distance(kline, dkline.s_macd_matched):
                self._30m_klines.loc[kline.name, 's_matched'] = True
                content = log_str.format(
                    trade_time, s, k_date_str, e5, e20, e60, close, macd)
                logger.info(content)
            else:
                self._30m_klines.loc[kline.name, 's_matched'] = False
        else:
            self._30m_klines.loc[kline.name, 's_matched'] = False
        return self._30m_klines.loc[kline.name, 's_matched']
