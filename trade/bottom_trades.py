from math import floor
from tqsdk import TargetPosTask, tafunc
from utils.bottom_trade_tools import get_date_str, get_date_str_short,\
        diff_two_value, calc_indicator, is_nline
from utils.common import LoggerGetter
from datetime import datetime, timedelta
from trade.utils import TradeUtilsLong, TradeUtilsShort, TradeUtils,\
        TradeUtilsData
from dao.entity import TradeStatusInfo
import numpy as np


class FutureTrade:
    '''期货交易基类，是多空交易类的父类。定义了一个期货交易对外开放的接口和内部
    主要方法。
    '''
    logger = LoggerGetter()

    def __init__(self, tsi: TradeStatusInfo, tud: TradeUtilsData):
        self._api = tud.api
        symbol = tsi.current_symbol
        position = self._api.get_position(symbol)
        self.tud = tud
        self._trade_tool = TargetPosTask(self._api, symbol)
        if tud.is_backtest:
            self._daily_klines = self._api.get_kline_serial(symbol, 60*60*24)
        else:
            self._daily_klines = self._api.get_kline_serial(
                symbol, 60*60*24).copy()
        self._h3_klines = self._api.get_kline_serial(symbol, 60*60*3)
        self._m30_klines = self._api.get_kline_serial(symbol, 60*30)
        self._utils: TradeUtils = self._create_utils(
            self._api.get_account(), position, tsi,
            self._api.get_quote(symbol), tud)
        self.calc_criteria(0)
        self._is_macd_match = False

    def _calc_open_pos_number(self) -> bool:
        utils = self._utils
        available = utils.account.balance * utils.open_pos_scale
        pos = floor(available / utils.quote.bid_price1)
        return pos

    def _can_open_ops(self):
        if self._match_dk_cond():
            if self._match_3hk_cond():
                if self._match_30mk_cond():
                    return True

    def _trade_pos(self, total_pos, sale_pos) -> int:
        '''final 方法，进行期货交易。开仓平仓，多空都适用。
        '''
        logger = self.logger
        ts = self._utils
        log_str = '{}交易,价格:{}手数:{}'
        target_pos = total_pos - sale_pos
        trade_time = ts.get_current_date_str()
        price = ts.quote.last_price
        if target_pos <= 0:
            target_pos = 0
        if not self.tud.just_check:
            self._trade_tool.set_target_volume(
                self._sale_target_pos(target_pos))
            while True:
                self._api.wait_update()
                if ts._get_tq_pos_number() == target_pos:
                    if sale_pos == 0:
                        logger.debug(log_str.format(
                            trade_time, price, total_pos))
                    else:
                        logger.debug(log_str.format(
                            trade_time, price, sale_pos))
                    break
        return target_pos

    def _closeout(self, sale_reason: str, is_switch=False) -> None:
        '''清仓售出
        '''
        self._sell_and_record_pos(self._utils.get_pos(),
                                  sale_reason, is_switch)

    def _sell_and_record_pos(self, sale_pos: int, sale_reason: str,
                             is_switch: bool) -> int:
        utils = self._utils
        price = utils.get_current_price()
        total_pos = utils.get_pos()
        rest_pos = self._trade_pos(total_pos, sale_pos)
        utils.set_close_info(price, sale_pos, sale_reason, is_switch)
        return rest_pos

    def _try_stop_loss(self) -> None:
        logger = self.logger
        utils = self._utils
        td = utils.tsi.trade_data
        trade_time = utils.get_current_date_str()
        price = utils.get_current_price()
        log_str = '{} {} <多空> {} 现价:{},止损价:{},手数:{}'
        if utils.get_stoplose_status():
            pos = self._utils.get_pos()
            content = log_str.format(
                trade_time, utils.tsi.current_symbol, td.slr,
                price, td.slp, pos)
            logger.info(content)
            self._closeout(utils.sl_message)

    def _try_open_pos(self) -> bool:
        ''' 开仓,当没有任何持仓并满足开仓条件时买入。
        子类可以利用该方法加入日志等逻辑
        '''
        utils = self._utils
        td = utils.tsi.trade_data
        # if utils.get_pos():
        #    return True
        if self._can_open_ops():
            logger = self.logger
            log_str = '{} {} <多空> 开仓 开仓价:{} {}手'
            open_pos = self._calc_open_pos_number()
            self._trade_pos(open_pos, 0)
            utils.set_open_info(open_pos)
            trade_time = utils.get_current_date_str()
            open_pos = utils.get_pos()
            content = log_str.format(
                trade_time, utils.tsi.current_symbol, td.price, open_pos)
            logger.info(content)
            return True
        return False

    def _try_sell_pos(self) -> None:
        ''' final 方法，尝试在开仓后进行止损或止盈。
        '''
        self._try_stop_loss()
        self._try_stop_profit()

    def _get_last_dk_line(self):
        return self._daily_klines.iloc[-2]

    def _get_s_last_h3_kline(self):
        return self._h3_klines.iloc[-2]

    def _get_last_h3_kline(self):
        kline = self._h3_klines.iloc[-2]
        symbol = self._utils.tsi.current_symbol
        while np.isnan(kline.datetime):
            self._api.wait_update()
            self._h3_klines = self._api.get_kline_serial(symbol, 60*60*3)
        return self._h3_klines.iloc[-2]

    def _get_s_last_m30_kline(self):
        return self._m30_klines.iloc[-2]

    def _get_last_m30_kline(self):
        kline = self._m30_klines.iloc[-2]
        symbol = self._utils.tsi.current_symbol
        while np.isnan(kline.datetime):
            self._api.wait_update()
            self._m30_klines = self._api.get_kline_serial(symbol, 60*30)
        return self._m30_klines.iloc[-2]

    def _has_checked(self, kline, test_name) -> bool:
        return (kline.get(test_name, default=-1) != -1
                and not (np.isnan(kline[test_name])))

    def get_Kline_values(self, kline) -> tuple:
        ema5 = kline.ema5
        ema20 = kline.ema20
        ema60 = kline.ema60
        macd = kline['MACD.close']
        close = kline.close
        open_p = kline.open
        trade_time = self._utils.get_current_date_str()
        return (ema5, ema20, ema60, macd, close, open_p, trade_time)

    def calc_criteria(self, k_type: int):
        '''计算某个周期的技术指标
        k_type 用来表示具体周期：
        1:日线，2:2小时线，3:30分钟线，4:5分钟线, 0: 技术以上全部均线
        '''
        if k_type == 1:
            calc_indicator(self._daily_klines)
        elif k_type == 2:
            calc_indicator(self._h3_klines)
        elif k_type == 3:
            calc_indicator(self._m30_klines)
        else:
            calc_indicator(self._daily_klines)
            calc_indicator(self._h3_klines)
            calc_indicator(self._m30_klines)

    def try_trade(self) -> None:
        ''' final 方法，交易类对外接口，
        每次行情更新时调用这个方法尝试交易
        '''
        if self._try_open_pos():
            self._try_sell_pos()

    def is_changing(self, k_type: int) -> bool:
        '''当某种K线生成新的记录时返回True
        k_type 代表K线类型
        0:代表当日交易结束的时刻
        1:生成新日线
        2:生成新3小时线
        3:生成新30分钟线
        4:生成新5分钟线
        '''
        if k_type == 1:
            return self._api.is_changing(
                self._daily_klines.iloc[-1], "datetime")
        elif k_type == 2:
            return self._api.is_changing(
                self._h3_klines.iloc[-1], "datetime")
        elif k_type == 3:
            return self._api.is_changing(
                self._m30_klines.iloc[-1], "datetime")
        elif k_type == 0:
            return self._api.is_changing(
                self._daily_klines.iloc[-1], "close")

    def finish(self):
        '''换月操作，代表当前交易已完成。
        如果当前合约交易有持仓，则全部平仓，
        并将tsi状态设置成下一个合约的初始状态
        '''
        logger = self.logger
        utils = self._utils
        tsi = utils.tsi
        logger.debug(tsi)
        if tsi.is_trading:
            hold_pos = tsi.trade_data.pos
            log_str = '换月清仓,售出数量{}'
            price = utils.quote.last_price
            self._trade_tool.set_target_volume(
                self._sale_target_pos(0))
            logger.info(log_str.format(hold_pos))
            utils.set_close_info(price, hold_pos, '换月平仓', True)
        else:
            tsi.switch_symbol(utils.get_current_date())
            utils.update_tsi()
        return self.create_new_one()


class FutureTradeShort(FutureTrade):
    '''做空交易类
    '''
    def _create_utils(self, account, position, tsi, quote, tud):
        return TradeUtilsShort(account, position, tsi, quote, tud)

    def _not_match_dk_cond(self) -> bool:
        # logger = self.logger
        # t_time = self._ts.get_current_date_str()
        # log_str = ('{} Last is N:{},Last2 is N:{},'
        #            'Last decline more then 2%:{},'
        #            'Last2 decline more than 2%:{}')
        # log_str2 = ('{} diff9_60:{},ema9:{},ema60:{},close:{}')
        l_kline = self._get_last_dk_line()
        # l2_kline = self._daily_klines.iloc[-3]
        # l3_kline = self._daily_klines.iloc[-4]
        e9, e22, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(l_kline)
        diff9_60 = diff_two_value(e9, e60)
        diff22_60 = diff_two_value(e22, e60)
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

    def _match_dk_cond(self) -> bool:
        '''做空日线条件检测
        合约交易日必须大于等于60天
        '''
        logger = self.logger
        kline = self._get_last_dk_line()
        utils = self._utils
        symbol = utils.tsi.current_symbol
        e9, e22, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(kline)
        daily_k_time = get_date_str_short(kline.datetime)
        log_str = ('{} {} <做空> 日线 K线时间:{} ema9:{} ema22:{} '
                   'ema60:{} 收盘:{} MACD:{}')
        is_match = False
        if e22 > e60 and macd < 0 and e22 > close:
            content = log_str.format(
                trade_time, symbol, daily_k_time,
                e9, e22, e60, close, macd)
            logger.info(content)
        return is_match

    def _match_3hk_cond(self) -> bool:
        '''做空3小时线检测
        '''
        logger = self.logger
        kline = self._get_s_last_h3_kline()
        utils = self._utils
        kline = self._get_last_h3_kline()
        e9, e22, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(kline)
        diffc_60 = diff_two_value(close, e60)
        diff9_60 = diff_two_value(e9, e60)
        diff22_60 = diff_two_value(e22, e60)
        kline_time = get_date_str(kline.datetime)
        log_str = ('{} {} <做空> {} 3小时条件 K线生成时间:{} '
                   'ema9:{} ema22:{} ema60:{} 收盘:{} 开盘{}'
                   'diffc_60:{} diff9_60:{} diff22_60{} MACD:{}')
        is_match = False
        if (e22 > e60 and
            (e22 > e9 or (e22 < e9 and close < e60 and open_p > e60)) and
           diff9_60 < 3 and diff22_60 < 3 and diffc_60 < 3 and macd < 0):
            self._h3_klines.loc[self._h3_klines.id == kline.id,
                                's_qualified'] = 1
            utils.set_last_h3_kline(kline)
            is_match = True
            match_str = '满足' if is_match else '不满足'
            content = log_str.format(
                trade_time, utils.tsi.current_symbol, match_str,
                kline_time, e9, e22,
                e60, close, open_p, diffc_60, diff9_60, diff22_60, macd)
            logger.info(content)
        return is_match

    def _match_30mk_cond(self) -> bool:
        '''做空30分钟线检测
        '''
        logger = self.logger
        kline = self._get_s_last_m30_kline()
        utils = self._utils
        kline = self._get_last_m30_kline()
        e9, e22, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(kline)
        diff22_60 = diff_two_value(e22, e60)
        diff9_60 = diff_two_value(e9, e60)
        kline_time = get_date_str(kline.datetime)
        log_str = ('{} {} <做空> 满足 30分钟条件:K线时间:{},ema9:{},'
                   'ema22:{},ema60:{},收盘:{},diff22_60:{},deff9_60:{},MACD:{}')
        if ((e60 > e22 > e9 or e22 > e60 > e9) and diff9_60 < 2
           and diff22_60 < 1 and macd < 0 and e60 > close
           and self.is_within_2days()):
            self._m30_klines.loc[self._m30_klines.id == kline.id,
                                 's_qualified'] = 1
            utils.set_last_m30_kline(kline)
            content = log_str.format(
                trade_time, utils.tsi.current_symbol, kline_time,
                e9, e22, e60, close, diff22_60, diff9_60, macd)
            logger.info(content)
            return True
        self._m30_klines.loc[self._m30_klines.id == kline.id,
                             's_qualified'] = 0
        return False

    def _sale_target_pos(self, target_pos) -> int:
        '''交易工具类需要的目标仓位，需要子类重写
        做多返回正数，做空返回负数
        '''
        return -target_pos

    def _try_stop_profit(self) -> None:
        logger = self.logger
        utils = self._utils
        symbol = utils.tsi.current_symbol
        td = utils.tsi.trade_data
        dk = self._get_last_dk_line()
        dks = []
        e9, e22, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(dk)
        diff22_60 = diff_two_value(e22, e60)
        log_str = ('{} {} <做空> 全部止赢,现价:{},手数:{},diff22_60:{},'
                   'close:{},macd:{}.之前符合条件K线日期{},macd{},'
                   'close:{},open:{}')
        utils.try_improve_sl_price()
        if utils.get_profit_status(dk):
            trade_time = utils.get_current_date_str()
            price = utils.get_current_price()
            if close > e9 and macd > 0:
                dks.append(self._daily_klines.iloc[-3])
                dks.append(self._daily_klines.iloc[-4])
                for t_dk in dks:
                    t_macd = t_dk['MACD.close']
                    if not is_nline(t_dk) and t_macd > 0:
                        sold_pos = td.pos
                        self._closeout('趋势止盈')
                        content = log_str.format(
                            trade_time, symbol, price, sold_pos,
                            diff22_60, close, macd, get_date_str_short(
                                t_dk.datetime),
                            t_macd, t_dk.close, t_dk.open
                        )
                        logger.info(content)
                        return
                td.stp = True
                utils.update_tsi()

    def trading_close_operation(self) -> None:
        '''弃用，主要进行收盘后的操作
        '''
        logger = self.logger
        utils = self._utils
        trade_time = utils.get_current_date_str()
        log_str = '{}<做空>{}开仓当天收盘价:{}大于EMA60:{},启动盈亏比止盈策略'
        if utils.tsi.is_trading:
            kline = self._daily_klines.iloc[-1]
            if self._pos.pos_short_today != 0:
                e9, e22, e60, macd, close, open_p, trade_time =\
                    self.get_Kline_values(kline)
                if close > e60:
                    utils.use_ps_ratio = True
                    utils.update_tsi()
                    logger.debug(
                        log_str.format(
                            trade_time,
                            self._symbol,
                            close,
                            e60))

    def is_within_2days(self) -> bool:
        logger = self.logger
        utils = self._utils
        trade_time = utils.get_current_date_str()
        log_str = ('{}<做空>{},当前日k线生成时间:{},最近一次30分钟收盘价与EMA60'
                   '交叉时间{},交叉前一根30分钟K线ema60:{},close:{}.')
        d_klines = self._daily_klines
        kline = d_klines.iloc[-1]
        last_dkline = self._get_last_dk_line()
        l30m_kline = d_klines.iloc[-9]
        c_date = tafunc.time_to_datetime(kline.datetime)
        temp_df = self._m30_klines.iloc[::-1]
        e60, close = 0, 0
        for i, temp_kline in temp_df.iterrows():
            _, _, e60, _, close, open_p, trade_time =\
                self.get_Kline_values(temp_kline)
            if close >= e60:
                # 30分钟收盘价和ema60还未交叉，不符合开仓条件
                if i == 199:
                    break
                else:
                    t30m_kline = self._m30_klines.iloc[i+1]
                    _, et22, et60, _, _, _, t_time =\
                        self.get_Kline_values(t30m_kline)
                    if et22 > et60:
                        l30m_kline = t30m_kline
                        break
        temp_date = tafunc.time_to_datetime(l30m_kline.datetime)
        # 当30分钟线生成时间小于21点，其所在日线为当日，否则为下一日日线
        if temp_date.hour < 21:
            l_date = tafunc.time_to_ns_timestamp(
                datetime(temp_date.year, temp_date.month, temp_date.day))
        else:
            l_date = tafunc.time_to_ns_timestamp(
                datetime(temp_date.year, temp_date.month,
                         temp_date.day)+timedelta(days=1))
        l_klines = d_klines[d_klines.datetime <= l_date]
        if not l_klines.empty:
            l_kline = l_klines.iloc[-1]
            logger.debug(log_str.format(
                trade_time, utils.tsi.current_symbol,
                c_date, temp_date, e60, close
            ))
            logger.debug(f'当前日线id:{kline.id},生成时间:{c_date},'
                         f'交叉当时K线id:{l_kline.id},生成时间:'
                         f'{tafunc.time_to_datetime(l_kline.datetime)}')
            limite_day = 2
            el9, el22, el60, _, cloes_l, _, _ =\
                self.get_Kline_values(last_dkline)
            if (diff_two_value(el22, el60) and cloes_l < el60
               or diff_two_value(el22, el60) > 5):
                limite_day = 3
            if kline.id - l_kline.id <= limite_day:
                logger.debug(
                    f'满足做空30分钟条件，两个日线间隔在{limite_day}日内。'
                )
                return True
        return False

    def create_new_one(self):
        return FutureTradeShort(self._utils.tsi, self.tud)


class FutureTradeLong(FutureTrade):
    '''做多交易类
    '''
    def _create_utils(self, account, position, tsi, quote, tud):
        return TradeUtilsLong(account, position, tsi, quote, tud)

    def _match_dk_cond(self) -> bool:
        '''做多日线条件检测
        合约交易日必须大于等于60天
        '''
        logger = self.logger
        kline = self._get_last_dk_line()
        utils = self._utils
        s = utils.tsi.current_symbol
        e5, e20, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(kline)
        daily_k_time = get_date_str_short(kline.datetime)

        log_str = ('{} {} <做多> 满足日线 K线时间:{} ema5:{} ema20:{} '
                   'ema60:{} 收盘:{} MACD:{}')
        is_match = False
        if self._has_checked(kline, 'l_qualified'):
            return kline['l_qualified']
        else:
            if e5 < e20 < e60 and close > e5:
                if macd > 0:
                    self._is_macd_match = True
                content = log_str.format(trade_time, s, daily_k_time,
                                         e5, e20, e60, close, macd)
                logger.info(content)
                is_match = True
        return is_match

    def _match_3hk_cond(self) -> bool:
        '''做多3小时线检测
        '''
        logger = self.logger
        kline = self._getLastDayLastH3Kline()
        if self._has_checked(kline, 'l_qualified'):
            return kline['l_qualified']
        utils = self._utils
        s = utils.tsi.current_symbol
        kline = self._get_last_h3_kline()
        e5, e20, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(kline)
        kline_time = get_date_str(kline.datetime)
        log_str = ('{} {} <做多> 3小时 K线时间:{}  MACD:{}')
        is_match = False
        if macd > 0:
            content = log_str.format(trade_time, s, kline_time, macd)
            logger.info(content)
            is_match = True
        return is_match

    def _getLastTradeDate(self) -> datetime:
        d_kline = self._get_last_dk_line()
        dk_time = tafunc.time_to_datetime(d_kline.datetime)
        return datetime(dk_time.year, dk_time.month, dk_time.day)

    def _getLastDayLastH3Kline(self):
        last_trade_date = self._getLastTradeDate()
        h3_klines = self._h3_klines
        lastday_lasth3k_time = last_trade_date.replace(hour=12)
        l_timestamp = tafunc.time_to_ns_timestamp(lastday_lasth3k_time)
        return h3_klines[h3_klines.datetime <= l_timestamp].iloc[-1]

    def _getLastDayLastM30Kline(self):
        last_trade_date = self._getLastTradeDate()
        m30_klines = self._m30_klines
        lastday_lasth3k_time = last_trade_date.replace(hour=14, minute=30)
        l_timestamp = tafunc.time_to_ns_timestamp(lastday_lasth3k_time)
        return m30_klines[m30_klines.datetime <= l_timestamp].iloc[-1]

    def _match_30mk_cond(self) -> bool:
        '''做多30分钟线检测
        '''
        logger = self.logger
        kline = self._getLastDayLastM30Kline()
        if self._has_checked(kline, 'l_qualified'):
            return kline['l_qualified']
        utils = self._utils
        s = utils.tsi.current_symbol
        e5, e20, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(kline)
        kline_time = get_date_str(kline.datetime)
        log_str = ('{} {} <做多> 30分钟条件 K线时间:{} ema5:{} ema20:{} '
                   'ema60:{} 收盘:{} MACD:{}')
        is_match = False
        if close > e60 and e5 > e60:
            if self.is_within_distance(kline):
                is_match = True
                content = log_str.format(
                    trade_time, s, kline_time, e5, e20, e60, close, macd)
                logger.info(content)
        return is_match

    def is_within_distance(self, l30m_kline) -> bool:
        logger = self.logger
        utils = self._utils
        trade_time = utils.get_current_date_str()
        log_str = ('{} {} <做多> 前一交易日最后30分钟线时间:{},满足条件的30分'
                   '钟线时间{},满足条件前一根30分钟线ema5:{},ema60:{},close:{}.')
        m30_klines = self._m30_klines
        m30_klines = m30_klines[
            m30_klines.datetime <= l30m_kline.datetime].iloc[::-1]
        wanted_kline = m30_klines.iloc[-10]
        distance = 5
        for i, t_kline in m30_klines.iterrows():
            e5, _, e60, _, close, _, _ =\
                self.get_Kline_values(t_kline)
            if close <= e60 or e5 <= e60:
                wanted_kline = self._m30_klines.iloc[i+1]
                content = log_str.format(
                    trade_time, utils.tsi.current_symbol,
                    get_date_str(l30m_kline.datetime),
                    get_date_str(wanted_kline.datetime),
                    e5, e60, close)
                logger.debug(content)
                break
        if self._is_macd_match:
            last_date = tafunc.time_to_datetime(l30m_kline.datetime)
            lastdate_timestamp = tafunc.time_to_ns_timestamp(
                datetime(last_date.year, last_date.month, last_date.day - 1,
                         21))
            if lastdate_timestamp <= wanted_kline.datetime:
                logger.debug('前一交易日MACD > 0, '
                             f'开始时间:{get_date_str(lastdate_timestamp)},'
                             f'满足条件30分钟线时间:'
                             f'{get_date_str(wanted_kline.datetime)}'
                             '符合在统一交易日的条件')
                return True
        else:
            if l30m_kline.id - wanted_kline.id < distance:
                logger.debug(f'上一交易日30分钟线id:{l30m_kline.id},'
                             f'满足条件的30分钟线id:{wanted_kline.id}'
                             '满足距离小于5的条件')
                return True
        return False

    def _sale_target_pos(self, target_pos) -> int:
        '''交易工具类需要的目标仓位，需要子类重写
        做多返回正数，做空返回负数
        '''
        return target_pos

    def _try_stop_profit(self) -> None:
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

    def create_new_one(self):
        return FutureTradeLong(self._utils.tsi, self.tud)
