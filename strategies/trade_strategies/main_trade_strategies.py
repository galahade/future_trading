from abc import abstractmethod
from datetime import datetime, timedelta
from tqsdk.objs import Order
from tqsdk import tafunc
from dao.odm.future_trade import MainIndicatorValues, MainTradeStatus
import dao.trade.trade_service as service
from strategies.entity import StrategyConfig
from strategies.trade_strategies.trade_strategies import (
    TradeStrategy, LongTradeStrategy, ShortTradeStrategy)
from utils.common_tools import LoggerGetter
import strategies.tools as tools
import utils.tqsdk_tools as tq_tools


class MainTradeStrategy(TradeStrategy):
    logger = LoggerGetter()

    def __init__(self, config: StrategyConfig, symbol: str):
        super().__init__(config, symbol)
        self._5m_klines = config.api.get_kline_serial(
            symbol, self.config.get5mK_Duration()
        )
        self._fill_indicators_by_type(0)

    def _fill_indicators_by_type(self, k_type: int):
        '''根据K线类型填充指标
        0: 全部K线
        1: 日线
        2: 3小时线
        3: 30分钟线
        4: 5分钟线
        '''
        if k_type == 0:
            self._fill_indicators_by_type(1)
            self._fill_indicators_by_type(2)
            self._fill_indicators_by_type(3)
            self._fill_indicators_by_type(4)
        elif k_type == 1:
            tools.fill_bottom_indicators(self._d_klines)
        elif k_type == 2:
            tools.fill_bottom_indicators(self._3h_klines)
        elif k_type == 3:
            tools.fill_bottom_indicators(self._30m_klines)
        elif k_type == 4:
            tools.fill_bottom_indicators(self._5m_klines)

    def _can_open_pos(self, is_in=True) -> bool:
        '''判断是否可以开仓'''
        logger = self.logger
        is_match = False
        if self.ts.trade_status == 0:
            if self._match_dk_condition():
                if self._match_3h_condition():
                    if self._match_30m_condition():
                        if self._match_5m_condition():
                            is_match = True
                            logger.info(
                                '<主策略>符合开仓条件, 请注意开仓提示'.ljust(100, '-'))
        return is_match

    def _try_stop_loss(self):
        '''当满足止损条件时，进行止损操作'''
        logger = self.logger
        trade_date_str = self._get_trade_date_str()
        price = self.quote.last_price
        log_str = '{} {} {} {} 现价:{} 止损价:{} 手数:{}'
        if self._has_match_stop_loss(price):
            pos = self.ts.carrying_volume
            content = log_str.format(
                trade_date_str, self.ts.symbol, self.ts.custom_symbol,
                self.ts.sold_condition.sl_reason, price,
                self.ts.sold_condition.stop_loss_price, pos)
            logger.info(content)
            self.closeout(0, self.ts.sold_condition.sl_reason)

    def _try_take_profit(self):
        '''当满足止盈条件时，进行止盈操作'''

    def _get_trade_status(self, symbol: str) -> MainTradeStatus:
        '''获取交易状态'''
        return service.get_main_trade_status(
            self.config.custom_symbol, symbol, self._get_direction(),
            self.config.quote.datetime)

    def _get_last_kline_in_trade(self, klines):
        return klines.iloc[-2]

    def _get_indicators(self, kline) -> tuple:
        ema9 = kline.ema9
        ema22 = kline.ema22
        ema60 = kline.ema60
        macd = kline['MACD.close']
        close = kline.close
        open_price = kline.open
        trade_time = self._get_trade_date()
        kline_time_str_short = tq_tools.get_date_str_short(kline.datetime)
        kline_time_str = tq_tools.get_date_str(kline.datetime)
        return (
            ema9, ema22, ema60, macd, close, open_price,
            trade_time, kline_time_str_short, kline_time_str)

    def is_within_2days(self) -> bool:
        logger = self.logger
        trade_time = self._get_trade_date_str()
        log_str = ('{} {} <做空> 当前日k线生成时间:{} 最近一次30分钟收盘价与EMA60'
                   '交叉时间{} 交叉前一根30分钟K线ema60:{} close:{}')
        daily_klines = self._d_klines
        c_dkline = daily_klines.iloc[-1]
        l_dkline = self._get_last_kline_in_trade(daily_klines)
        l30m_kline = daily_klines.iloc[-9]
        c_date = tq_tools._get_datetime_from_ns(c_dkline.datetime)
        temp_df = self._m30_klines.iloc[::-1]
        e60, close = 0, 0
        for i, temp_kline in temp_df.iterrows():
            _, _, e60, _, close, _, trade_time =\
                self._get_indicators(temp_kline)
            if close >= e60:
                # 30分钟收盘价和ema60还未交叉，不符合开仓条件
                if i == 199:
                    break
                else:
                    t30m_kline = self._30m_klines.iloc[i+1]
                    _, et22, et60, _, _, _, _ =\
                        self._get_indicators(t30m_kline)
                    if et22 > et60:
                        l30m_kline = t30m_kline
                        break
        temp_date = tq_tools._get_datetime_from_ns(l30m_kline.datetime)
        # 当30分钟线生成时间小于21点，其所在日线为当日，否则为下一日日线
        if temp_date.hour < 21:
            l_date = tafunc.time_to_ns_timestamp(
                datetime(temp_date.year, temp_date.month, temp_date.day))
        else:
            l_date = tafunc.time_to_ns_timestamp(
                datetime(temp_date.year, temp_date.month,
                         temp_date.day)+timedelta(days=1))
        l_klines = daily_klines[daily_klines.datetime <= l_date]
        if not l_klines.empty:
            l_kline = l_klines.iloc[-1]
            logger.debug(log_str.format(
                trade_time, self.ts.symbol, c_date, temp_date, e60, close))
            logger.debug(f'当前日线id:{c_dkline.id},生成时间:{c_date},'
                         f'交叉当时K线id:{l_kline.id},生成时间:'
                         f'{tafunc.time_to_datetime(l_kline.datetime)}')
            limite_day = 2
            _, el22, el60, _, cloes_l, _, _ =\
                self._get_indicators(l_dkline)
            if (tools.diff_two_value(el22, el60) and cloes_l < el60
               or tools.diff_two_value(el22, el60) > 5):
                limite_day = 3
            if c_dkline.id - l_kline.id <= limite_day:
                logger.debug(
                    f'满足做空30分钟条件，两个日线间隔在{limite_day}日内。'
                )
                return True
        return False

    def _match_3hk_c2_distance(self) -> bool:
        # logger = self.logger
        klines = self._3h_klines.iloc[::-1]
        # log_str = 'k2:{},e9:{},e60:{},date:{}/k1:{},e22:{},e60:{},date:{}'
        k1, k2 = 0, 0
        is_done_1 = False
        for _, kline in klines.iterrows():
            # logger.debug(f'kline:{kline}')
            e9 = kline.ema9
            e22 = kline.ema22
            e60 = kline.ema60
            if not is_done_1 and e22 <= e60:
                k1 = kline.id
                # date1 = get_date_str(kline.datetime)
                # ema22 = e22
                # ema60_1 = e60
                is_done_1 = True
                # logger.debug(log_debug_1.format(
                #    k1, e9, e22, e60, date1
                # ))
            if e9 <= e60:
                k2 = kline.id
                # date2 = get_date_str(kline.datetime)
                # ema9 = e9
                # ema60_2 = e60
                # logger.debug(log_debug_2.format(
                #    k2, e9, e22, e60, date2
                # ))
                break
        if 0 <= k1 - k2 <= 5:
            # logger.debug(log_str.format(
            # k2, ema9, ema60_2, date2, k1, ema22, ema60_1, date1))
            # logger.debug('两个交点距离小于等于5,符合条件')
            return True
        return False

    def _set_open_condition(self, kline, cond_num: int,
                            indiatorValues: MainIndicatorValues):
        '''设置开仓条件'''
        e9, e22, e60, macd, close, open_p, trade_time =\
            self._get_indicators(kline)
        indiatorValues.ema9 = e9
        indiatorValues.ema22 = e22
        indiatorValues.ema60 = e60
        indiatorValues.macd = macd
        indiatorValues.close = close
        indiatorValues.open = open_p
        indiatorValues.kline_time = trade_time
        indiatorValues.condition_id = cond_num
    
    def _set_sold_condition(self, order: Order):
        s_c = self.ts.sold_condition
        s_c.take_profit_stage = 0

    @abstractmethod
    def _match_dk_condition(self, is_in=True) -> bool:
        '''做多日线条件检测 '''

    @abstractmethod
    def _match_3h_condition(self, is_in=True) -> bool:
        pass

    @abstractmethod
    def _match_30m_condition(self, is_in=True) -> bool:
        pass

    @abstractmethod
    def _match_5m_condition(self, is_in=True) -> bool:
        pass

    @abstractmethod
    def _has_match_stop_loss(self, price: float) -> bool:
        pass


class MainLongTradeStrategy(MainTradeStrategy, LongTradeStrategy):

    def _try_take_profit(self):
        '''当满足止盈条件时，进行止盈操作'''

    def _match_dk_condition(self, is_in=True) -> bool:
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._d_klines)
        e9, e22, e60, macd, close, open_p, trade_time, k_date_str_short =\
            self._get_indicators(kline)
        log_str = ('{} {} <做多> 满足日线{} K线时间:{} ema9:{} ema22:{} '
                   'ema60:{} 收盘:{} diff9_60:{} diffc_60:{} diff22_60:{} '
                   'MACD:{}')
        cond_number = 0
        if tools.has_set_k_attr(kline, 'l_condition'):
            return kline.l_condition
        diff9_60 = tools.diff_two_value(e9, e60)
        diffc_60 = tools.diff_two_value(close, e60)
        diff22_60 = tools.diff_two_value(e22, e60)
        if e22 < e60:
            # 日线条件1
            if ((diff9_60 < 1 or diff22_60 < 1) and close > e60 and
               macd > 0 and (e9 > e22 or macd > 0)):
                cond_number = 1
        elif e22 > e60:
            # 日线条件2
            if diff22_60 < 1 and close > e60:
                cond_number = 2
            # 日线条件3
            elif (1 < diff9_60 < 3 and e9 > e22 and
                    e22 > min(open_p, close) > e60):
                cond_number = 3
            # 日线条件4
            elif (1 < diff22_60 < 3 and diff9_60 < 2 and e22 > close > e60
                    and e22 > e9 > e60):
                cond_number = 4
            # 日线条件5
            elif (diff22_60 > 3 and diffc_60 < 3 and
                    e22 > close > e60 and e22 > open_p > e60):
                cond_number = 5
        self._set_klines_value(
            self._d_klines, kline.name, 'l_condition', cond_number)
        if cond_number > 0:
            content = log_str.format(
                trade_time, self.ts.symbol, cond_number, k_date_str_short,
                e9, e22, e60, close, diff9_60, diffc_60, diff22_60, macd)
            logger.info(content)
            self._set_open_condition(
                kline, cond_number, self.ts.open_condition.daily_condition)
            self.ts.open_condition.daily_condition = cond_number
        return self._d_klines[kline.name].l_condition

    def _match_3h_condition(self, is_in=True) -> bool:
        '''做多3小时线检测
        '''
        logger = self.logger
        dkline = self._get_last_kline_in_trade(self._d_klines)
        kline = self._get_last_kline_in_trade(self._3h_klines)
        if tools.has_set_k_attr(kline, 'l_condition'):
            return kline.l_condition
        e9, e22, e60, macd, close, open_p, trade_time, _, k_date_str =\
            self._get_indicators(kline)
        diffc_60 = tools.diff_two_value(close, e60)
        diffo_60 = tools.diff_two_value(open_p, e60)
        diff22_60 = tools.diff_two_value(e22, e60)
        diff9_60 = tools.diff_two_value(e9, e60)
        log_str = ('{} {} <做多> 满足3小时{}: K线时间:{} '
                   'ema9:{} ema22:{} ema60:{} 收盘:{} 开盘:{} '
                   'diffc_60:{} diffo_60:{} diff22_60{} MACD:{}')
        cond_number = 0
        if diffc_60 < 3 or diffo_60 < 3:
            if dkline.l_condition in [1, 2]:
                if (e22 < e60 and e9 < e60 and
                    (diff22_60 < 1 or
                     (1 < diff22_60 < 2 and (macd > 0 or close > e60)))):
                    cond_number = 1
                elif close > e9 > e22 > e60:
                    if self._match_3hk_c2_distance():
                        cond_number = 2
                elif diff9_60 < 1 and diff22_60 < 1 and macd > 0:
                    cond_number = 5
            elif dkline.l_condition in [3, 4]:
                if (close > e60 > e22 and macd > 0 and diff22_60 < 1 and e9 <
                   e60):
                    cond_number = 3
                elif (dkline.l_condition == 3 and diff9_60 < 1
                      and diff22_60 < 1):
                    cond_number = 6
            elif dkline.l_condition == 5 and (e60 > e22 > e9):
                cond_number = 4
        self._set_klines_value(
            self._3h_klines, kline.name, 'l_condition', cond_number)
        if cond_number > 0:
            content = log_str.format(
                trade_time, self.ts.symbol, cond_number, k_date_str, e9, e22,
                e60, close, open_p, diffc_60, diffo_60, diff22_60, macd)
            logger.info(content)
            self._set_open_condition(
                kline, cond_number, self.ts.open_condition.hourly_condition)
        return self._3h_klines[kline.name].l_condition

    def _match_30m_condition(self, is_in=True) -> bool:
        '''做多30分钟线检测'''
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._30m_klines)
        if tools.has_set_k_attr(kline, 'l_condition'):
            return kline.l_condition
        e9, e22, e60, macd, close, _, trade_time, k_date_str =\
            self._get_indicators(kline)
        diffc_60 = tools.diff_two_value(close, e60)
        log_str = ('{} {} <做多> 满足30分钟条件 K线时间:{} ema9:{} ema22:{} '
                   'ema60:{} 收盘:{} diffc_60:{} MACD:{}')
        if close > e60 and macd > 0 and diffc_60 < 1.2:
            self._set_klines_value(
                self._30m_klines, kline.name, 'l_condition', 1)
            content = log_str.format(
                trade_time, self.ts.symbol, k_date_str, e9, e22, e60,
                close, diffc_60, macd)
            logger.info(content)
            self._set_open_condition(
                kline, 1, self.ts.open_condition.minute_30_condition)
        else:
            self._set_klines_value(
                self._30m_klines, kline.name, 'l_condition', 0)
        return self._30m_klines[kline.name].l_condition

    def _match_5m_condition(self, is_in=True) -> bool:
        '''做多5分钟线检测
        '''
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._5m_klines)
        if tools.has_set_k_attr(kline, 'l_condition'):
            return kline.l_condition
        e9, e22, e60, macd, close, _, trade_time, k_date_str =\
            self._get_indicators(kline)
        diffc_60 = tools.diff_two_value(close, e60)
        log_str = ('{} {} <做多> 满足5分钟条件 K线时间:{} '
                   'ema9:{} ema22:{} ema60:{} 收盘:{} diffc_60:{} MACD:{}')
        if close > e60 and macd > 0 and diffc_60 < 1.2:
            self._set_klines_value(
                self._5m_klines, kline.name, 'l_condition', 1)
            content = log_str.format(
                trade_time, self.ts.symbol, k_date_str, e9, e22, e60,
                close, diffc_60, macd)
            logger.info(content)
            self._set_open_condition(
                kline, 1, self.ts.open_condition.minute_5_condition)
            return True
        else:
            self._set_klines_value(
                self._5m_klines, kline.name, 'l_condition', 0)
        return self._5m_klines[kline.name].l_condition

    def _has_match_stop_loss(self, price: float) -> bool:
        matched = False
        if self.ts.trade_status == 1:
            sold_cond = self.ts.sold_condition
            if price <= sold_cond.stop_loss_price:
                matched = True
        return matched

    def _set_sold_condition(self, order: Order):
        super()._set_sold_condition(order)
        o_c = self.ts.open_condition
        s_c = self.ts.sold_condition
        if o_c.daily_condition in [1, 2]:
            s_c.take_profit_cond = 1
        elif o_c.daily_condition == 5:
            s_c.take_profit_cond = 2
        elif o_c.daily_condition == 3 and o_c.hourly_condition == 6:
            s_c.take_profit_cond = 3
        elif o_c.daily_condition in [3, 4] and o_c.hourly_condition == 3:
            s_c.take_profit_cond = 4

    def _set_sold_prices(self, order: Order):
        s_c = self.ts.sold_condition
        s_c.stop_loss_price = self._calc_price(
            order.trade_price, self.config.f_info.long_config.stop_loss_scale,
            False)
        if s_c.take_profit_cond in [1, 2, 3]:
            s_c.tp_started_point = self._calc_price(
                order.trade_price,
                self.config.f_info.long_config.profit_start_scale_1,
                True)
        elif s_c.take_profit_cond == 4:
            s_c.tp_started_point = self._calc_price(
                order.trade_price,
                self.config.f_info.long_config.profit_start_scale_2,
                True)
        self.logger.info(f'{self._get_trade_date_str()}'
                         f'<做多>开仓价:{order.trade_price}'
                         f'止损设为:{s_c.stop_loss_price}'
                         f'止盈起始价为:{s_c.tp_started_point}')


class MainShortTradeStrategy(MainTradeStrategy, ShortTradeStrategy):
    def _try_take_profit(self):
        '''当满足止盈条件时，进行止盈操作'''
        logger = self.logger
        utils = self._utils
        td = utils.tsi.trade_data
        s = utils.tsi.current_symbol
        dk = self._get_last_dk_line()
        log_str = "{} {} <做多> 止赢{},现价:{},手数:{},剩余仓位:{},止赢起始价:{}"
        sp_log = '止盈{}-售出{}'
        trade_time = utils.get_current_date_str()
        price = utils.get_current_price()
        if utils.get_profit_status() in [1, 2, 3]:
            utils.try_improve_sl_price()
            if utils.is_final5_closeout(dk):
                sold_pos = utils.get_pos()
                self._closeout(sp_log.format(td.p_cond, '100%'))
                content = log_str.format(
                    trade_time, s, td.p_cond, price, sold_pos, 0, td.spp)
                logger.info(content)
        elif utils.get_profit_status() in [4]:
            if td.p_stage == 1:
                td.p_stage = 2
                sold_pos = utils.get_pos()//2
                rest_pos = self._sell_and_record_pos(
                    sold_pos, sp_log.format(td.p_cond, '50%'), False)
                content = log_str.format(
                    trade_time, s, td.p_cond, price,
                    sold_pos, rest_pos, td.spp)
                logger.info(content)
                utils.update_tsi()
            elif td.p_stage == 2:
                if (utils.get_current_price() >=
                   utils.calc_price(td.price, True, 3)):
                    sold_pos = utils.get_pos()
                    self._closeout(sp_log.format(td.p_cond, '剩余全部'))
                    content = log_str.format(
                        trade_time, s, td.p_cond, price, sold_pos, 0, td.spp)
                    logger.info(content)

    def _match_dk_condition(self, is_in=True) -> bool:
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._d_klines)
        if tools.has_set_k_attr(kline, 's_condition'):
            return kline.s_condition
        s = self.ts.symbol
        (e9, e22, e60, macd, close, _, trade_time,
            k_date_str_short) = self._get_indicators(kline)
        log_str = ('{} {} <做空> 满足日线 K线时间:{} ema9:{} ema22:{} '
                   'ema60:{} 收盘:{} MACD:{}')
        content = log_str.format(
            trade_time, s, k_date_str_short,
            e9, e22, e60, close, macd)
        # 日线条件
        if e22 > e60 and macd < 0 and e22 > close:
            # logger.debug(f'kline column:{kline}')
            is_matched = not self._no_matched_open_cond()
            if is_matched:
                self._set_klines_value(
                    self._d_klines, kline.name, 's_condition', 1)
                logger.info(content)
                self._set_open_condition(
                    kline, 1, self.ts.open_condition.daily_condition)
            else:
                self._set_klines_value(
                    self._d_klines, kline.name, 's_condition', 0)
        else:
            self._set_klines_value(
                self._d_klines, kline.name, 's_condition', 0)
        return self._d_klines.loc[kline.name, 's_condition']

    def _no_matched_open_cond(self) -> bool:
        # logger = self.logger
        # t_time = self._ts.get_current_date_str()
        # log_str = ('{} Last is N:{},Last2 is N:{},'
        #            'Last decline more then 2%:{},'
        #            'Last2 decline more than 2%:{}')
        # log_str2 = ('{} diff9_60:{},ema9:{},ema60:{},close:{}')
        l_kline = self._get_last_kline_in_trade(self._d_klines)
        # l2_kline = self._daily_klines.iloc[-3]
        # l3_kline = self._daily_klines.iloc[-4]
        e9, e22, e60, _, close, _, _ = self._get_indicators(l_kline)
        diff9_60 = tools.diff_two_value(e9, e60)
        diff22_60 = tools.diff_two_value(e22, e60)
        if diff9_60 < 2 or diff22_60 < 2:
            if e60 < close:
                # logger.debug(log_str2.format(
                #     t_time, diff9_60, e9, e60, close))
                return True
        # if diff9_60 < 3:
        #     l_n = is_nline(l_kline)
        #     l2_n = is_nline(l2_kline)
        #     l_d2 = is_decline_2p(l_kline, l2_kline)
        #     l2_d2 = is_decline_2p(l2_kline, l3_kline)
        #     if (l_n and l2_n) or (l_d2 or l2_d2):
        #         logger.debug(log_str.format(t_time, l_n, l2_n, l_d2, l2_d2))
        #         return True
        return False

    def _match_3h_condition(self, is_in=True) -> bool:
        '''做空3小时线检测
        '''
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._3h_klines)
        if tools.has_set_k_attr(kline, 's_condition'):
            return kline.s_condition
        e9, e22, e60, macd, close, open_p, trade_time, _, k_date_str =\
            self._get_indicators(kline)
        diffc_60 = tools.diff_two_value(close, e60)
        diff9_60 = tools.diff_two_value(e9, e60)
        diff22_60 = tools.diff_two_value(e22, e60)
        log_str = ('{} {} <做空> 满足3小时 K线时间:{} '
                   'ema9:{} ema22:{} ema60:{} 收盘:{} 开盘:{}'
                   'diffc_60:{} diff9_60:{} diff22_60{} MACD:{}')
        if (e22 > e60 and
            (e22 > e9 or (e22 < e9 and close < e60 and open_p > e60)) and
           diff9_60 < 3 and diff22_60 < 3 and diffc_60 < 3 and macd < 0):
            self._set_klines_value(
                self._3h_klines, kline.name, 's_condition', 1)
            content = log_str.format(
                trade_time, self.ts.symbol, k_date_str, e9, e22,
                e60, close, open_p, diffc_60, diff9_60, diff22_60, macd)
            logger.info(content)
            self._set_open_condition(
                kline, 1, self.ts.open_condition.hourly_condition)
        else:
            self._set_klines_value(
                self._3h_klines, kline.name, 's_condition', 0)
        return self._3h_klines.loc[kline.name, 's_condition']

    def _match_30m_condition(self, is_in=True) -> bool:
        '''做空30分钟线检测
        '''
        logger = self.logger
        kline = self._get_last_kline_in_trade(self._30m_klines)
        if tools.has_set_k_attr(kline, 's_condition'):
            return kline.s_condition
        e9, e22, e60, macd, close, _, trade_time, _, k_date_str =\
            self._get_indicators(kline)
        diff22_60 = tools.diff_two_value(e22, e60)
        diff9_60 = tools.diff_two_value(e9, e60)
        log_str = ('{} {} <做空> 满足30分钟 K线时间:{} ema9:{} '
                   'ema22:{} ema60:{} 收盘:{} diff22_60:{} deff9_60:{} MACD:{}')
        if ((e60 > e22 > e9 or e22 > e60 > e9) and diff9_60 < 2
           and diff22_60 < 1 and macd < 0 and e60 > close
           and self.is_within_2days()):
            self._set_klines_value(
                self._30m_klines, kline.name, 's_condition', 1)
            content = log_str.format(
                trade_time, self.ts.symbol, k_date_str,
                e9, e22, e60, close, diff22_60, diff9_60, macd)
            logger.info(content)
            self._set_open_condition(
                kline, 1, self.ts.open_condition.minute_30_condition
            )
        else:
            self._set_klines_value(
                self._30m_klines, kline.name, 's_condition', 0)
        return self._30m_klines.loc[kline.name, 's_condition']

    def _match_5m_condition(self, is_in=True) -> bool:
        return True

    def _has_match_stop_loss(self, price: float) -> bool:
        matched = False
        if self.ts.trade_status == 1:
            sold_cond = self.ts.sold_condition
            if price >= sold_cond.stop_loss_price:
                matched = True
        return matched

    def _set_sold_prices(self, order: Order):
        s_c = self.ts.sold_condition
        s_c.stop_loss_price = self._calc_price(
            order.trade_price, self.config.f_info.short_config.stop_loss_scale,
            True)
        s_c.tp_started_point = self._calc_price(
            order.trade_price,
            self.config.f_info.short_config.profit_start_scale,
            False)
        self.logger.info(f'{self._get_trade_date_str()}'
                         f'<做空>开仓价:{order.trade_price}'
                         f'止损设为:{s_c.stop_loss_price}'
                         f'止盈起始价为:{s_c.tp_started_point}')
