from math import ceil
from tqsdk import TargetPosTask, tafunc
from utils.bottom_trade_tools import get_date_str, get_date_str_short,\
        diff_two_value, calc_indicator, is_nline
from utils.common import LoggerGetter
from datetime import datetime, timedelta
from trade.bottom_utils import TradeUtilsLong, TradeUtilsShort, TradeUtils,\
        TradeUtilsData
from dao.entity import TradeStatusInfo
from dao.condition_entity import BottomConditionInfo, BottomCommonCondition
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
        self._is_long_macd_match = False
        self._is_short_macd_match = False
        self._has_traded = False
        self.bci = BottomConditionInfo(self._utils.tsi.custom_symbol, symbol)

    def _calc_open_pos(self, price) -> int:
        utils = self._utils
        available = utils.account.balance * utils.open_pos_scale
        pos = ceil(available / price)
        return pos

    def _calc_open_pos_number(self) -> int:
        return self._calc_open_pos(self._utils.quote.bid_price1)

    def _can_open_ops(self, is_predicted=False):
        logger = self.logger
        is_match = False
        if self._utils.get_pos() == 0:
            if self._match_dk_cond(is_predicted):
                if self._match_3hk_cond(is_predicted):
                    if self._match_30mk_cond(is_predicted):
                        if is_predicted:
                            logger.info(
                                '请注意以下开仓提示'.ljust(100, '-'))
                        else:
                            logger.info(
                                '满足开仓条件，准备开仓'.ljust(100, '-'))
                        is_match = True
        return is_match

    def _trade_pos(self, total_pos, sale_pos) -> int:
        '''final 方法，进行期货交易。开仓平仓，多空都适用。
        '''
        logger = self.logger
        ts = self._utils
        log_str = '{} 完成交易,价格:{}手数:{}'
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
        log_str = '{} {} {} {} 现价:{},止损价:{},手数:{}'
        utils.try_improve_sl_price()
        if utils.get_stoplose_status():
            pos = self._utils.get_pos()
            content = log_str.format(
                trade_time, utils.tsi.current_symbol,
                utils.tsi.custom_symbol, td.slr,
                price, td.slp, pos)
            logger.info(content)
            self._closeout(utils.sl_message)

    def _has_open_pos(self) -> bool:
        ''' 开仓,当没有任何持仓并满足开仓条件时买入。
        子类可以利用该方法加入日志等逻辑
        '''
        logger = self.logger
        utils = self._utils
        td = utils.tsi.trade_data
        is_match = False
        if utils.get_pos() and self._has_traded:
            is_match = True
        elif self._has_traded:
            is_match = False
        elif utils.get_pos():
            is_match = True
        elif self._can_open_ops():
            log_str = '{} {} {} 开仓 开仓价:{} {}手'
            open_pos = self._calc_open_pos_number()
            self._trade_pos(open_pos, 0)
            utils.set_open_info(open_pos)
            trade_time = utils.get_current_date_str()
            open_pos = utils.get_pos()
            content = log_str.format(
                trade_time, utils.tsi.current_symbol,
                utils.tsi.custom_symbol, td.price, open_pos)
            logger.info(content)
            is_match = True
        self._has_traded = True
        return is_match

    def _try_sell_pos(self) -> None:
        ''' final 方法，尝试在开仓后进行止损或止盈。
        '''
        self._try_stop_loss()
        # self._try_stop_profit()

    def _get_last_dk_line(self, is_predicted=False):
        if is_predicted:
            return self._daily_klines.iloc[-1]
        else:
            return self._daily_klines.iloc[-2]

    def _get_last_h3_kline(self):
        kline = self._h3_klines.iloc[-2]
        symbol = self._utils.tsi.current_symbol
        while np.isnan(kline.datetime):
            self._api.wait_update()
            self._h3_klines = self._api.get_kline_serial(symbol, 60*60*3)
        return self._h3_klines.iloc[-2]

    def _has_checked(self, kline, test_name) -> bool:
        return (kline.get(test_name, default=-1) != -1
                and not (np.isnan(kline[test_name])))

    def _getLastTradeDate(self, is_predicted=False) -> datetime:
        d_kline = self._get_last_dk_line(is_predicted)
        dk_time = tafunc.time_to_datetime(d_kline.datetime)
        return datetime(dk_time.year, dk_time.month, dk_time.day)

    def _getLastDayLastH3Kline(self, is_predicted=False):
        last_trade_date = self._getLastTradeDate(is_predicted)
        h3_klines = self._h3_klines
        lastday_lasth3k_time = last_trade_date.replace(hour=12)
        l_timestamp = tafunc.time_to_ns_timestamp(lastday_lasth3k_time)
        return h3_klines[h3_klines.datetime <= l_timestamp].iloc[-1]

    def _getLastDayLastM30Kline(self, is_predicted=False):
        last_trade_date = self._getLastTradeDate(is_predicted)
        m30_klines = self._m30_klines
        lastday_lasth3k_time = last_trade_date.replace(hour=14, minute=30)
        l_timestamp = tafunc.time_to_ns_timestamp(lastday_lasth3k_time)
        return m30_klines[m30_klines.datetime <= l_timestamp].iloc[-1]

    def _is_within_distance(self, m30_kline, is_macd_match) -> bool:
        logger = self.logger
        utils = self._utils
        trade_time = utils.get_current_date_str()
        log_str = ('{} {} 前一交易日最后30分钟线时间:{},满足条件的30分'
                   '钟线时间{},满足条件前一根30分钟线ema5:{},ema60:{},close:{}.')
        m30_klines = self._m30_klines
        m30_klines = m30_klines[
            m30_klines.datetime < m30_kline.datetime].iloc[::-1]
        wanted_kline = m30_klines.iloc[-10]
        distance = 5
        is_match = False
        for i, t_kline in m30_klines.iterrows():
            e5, _, e60, _, close, _, _ =\
                self.get_Kline_values(t_kline)
            if close <= e60 or e5 <= e60:
                wanted_kline = self._m30_klines.iloc[i+1]
                content = log_str.format(
                    trade_time, utils.tsi.current_symbol,
                    get_date_str(m30_kline.datetime),
                    get_date_str(wanted_kline.datetime),
                    e5, e60, close)
                logger.debug(content)
                break
        if is_macd_match:
            last_date = tafunc.time_to_datetime(m30_kline.datetime)
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
            if m30_kline.id - wanted_kline.id < distance:
                logger.debug(f'上一交易日30分钟线id:{m30_kline.id},'
                             f'满足条件的30分钟线id:{wanted_kline.id}'
                             '满足距离小于5的条件')
                is_match = True
        return is_match

    def _check_openpos_situation(self):
        logger = self.logger
        ts = self._utils
        if ts.get_pos():
            log_open = '{} {} {} 已持仓，仓位:{}手，价格:{}, 止损价:{}'
            tsi = ts.tsi
            logger.info(log_open.format(
                ts.get_current_date_str(),
                ts.tsi.current_symbol,
                tsi.custom_symbol,
                tsi.trade_data.pos,
                tsi.trade_data.price,
                tsi.trade_data.slp,
            ))

    def close_operation(self):
        self._has_traded = False

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
        if self._has_open_pos():
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

    def before_open_operation(self):
        '''每次程序运行执行一次，用来检查当天是否有需要开仓的品种
        目前由于天勤只能在临近开盘时产生下一个交易日K线，而该方法需要
        在收盘后即运行，故其判断开仓使用的日K线有别于开盘后进行交易使用的
        日K线
        '''
        logger = self.logger
        utils = self._utils
        self._check_openpos_situation()
        if self._can_open_ops(is_predicted=True):
            log_str = ('{} {} {} 符合开仓条件, 开盘后注意关注开仓 '
                       '前一日收盘价:{}, 预计开仓:{} 手')
            bci = self.bci
            bci.last_price = self._get_last_dk_line(True).close
            bci.pos = self._calc_open_pos(bci.last_price)
            bci.balance = utils.account.balance
            bci.open_pos_scale = utils.tud.future_config.open_pos_scale
            bci.contract_m = utils.tud.future_config.contract_m
            trade_time = utils.get_current_date_str()
            content = log_str.format(
                trade_time, bci.symbol,
                bci.custom_symbol, bci.last_price, bci.pos)
            logger.info(content)
            self._utils.store_condition_info(self.bci)


class FutureTradeShort(FutureTrade):
    '''做空交易类
    '''
    def _create_utils(self, account, position, tsi, quote, tud):
        return TradeUtilsShort(account, position, tsi, quote, tud)

    def _match_dk_cond(self, is_predicted=False) -> bool:
        '''做空日线条件检测
        合约交易日必须大于等于60天
        '''
        logger = self.logger
        kline = self._get_last_dk_line(is_predicted)
        utils = self._utils
        s = utils.tsi.current_symbol
        e5, e20, e60, macd, close, _, trade_time =\
            self.get_Kline_values(kline)
        daily_k_time = get_date_str_short(kline.datetime)
        log_str = ('{} {} <做空> 满足日线 K线时间:{} ema5:{} ema20:{} '
                   'ema60:{} 收盘:{} MACD:{}')
        is_match = False
        if e5 > e20 > e60 and close < e5:
            if macd < 0:
                self._is_short_macd_match = True
            content = log_str.format(
                trade_time, s, daily_k_time, e5, e20, e60, close, macd)
            logger.info(content)
            self.bci.setDayCByKline(kline)
            is_match = True
        return is_match

    def _match_3hk_cond(self, is_predicted=False) -> bool:
        '''做空3小时线检测
        '''
        logger = self.logger
        kline = self._getLastDayLastH3Kline(is_predicted)
        utils = self._utils
        e5, e20, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(kline)
        kline_time = get_date_str(kline.datetime)
        log_str = ('{} {} <做空> 满足3小时 K线时间:{} MACD:{}')
        is_match = False
        if macd < 0:
            content = log_str.format(
                trade_time, utils.tsi.current_symbol, kline_time, macd)
            logger.info(content)
            self.bci.setHoursByKline(kline)
            is_match = True
        return is_match

    def _match_30mk_cond(self, is_predicted=False) -> bool:
        '''做空30分钟线检测
        '''
        logger = self.logger
        kline = self._getLastDayLastM30Kline(is_predicted)
        utils = self._utils
        s = utils.tsi.current_symbol
        e5, e20, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(kline)
        kline_time = get_date_str(kline.datetime)
        log_str = ('{} {} <做空> 满足30分钟条件 K线时间:{} ema5:{} ema20:{} '
                   'ema60:{} 收盘:{} MACD:{}')
        is_match = False
        if close < e60 and e5 < e60:
            if self._is_within_distance(kline, self._is_short_macd_match):
                is_match = True
                self.bci.setMinutesCByKline(kline)
                content = log_str.format(
                    trade_time, s, kline_time, e5, e20, e60, close, macd)
                logger.info(content)
        return is_match

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

    def create_new_one(self):
        return FutureTradeShort(self._utils.tsi, self.tud)


class FutureTradeLong(FutureTrade):
    '''做多交易类
    '''
    def _create_utils(self, account, position, tsi, quote, tud):
        return TradeUtilsLong(account, position, tsi, quote, tud)

    def _match_dk_cond(self, is_predicted=False) -> bool:
        '''做多日线条件检测
        合约交易日必须大于等于60天
        '''
        logger = self.logger
        kline = self._get_last_dk_line(is_predicted)
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
                    self._is_long_macd_match = True
                content = log_str.format(trade_time, s, daily_k_time,
                                         e5, e20, e60, close, macd)
                logger.info(content)
                self.bci.setDayCByKline(kline)
                is_match = True
        return is_match

    def _match_3hk_cond(self, is_predicted=False) -> bool:
        '''做多3小时线检测
        '''
        logger = self.logger
        kline = self._getLastDayLastH3Kline(is_predicted)
        utils = self._utils
        s = utils.tsi.current_symbol
        e5, e20, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(kline)
        kline_time = get_date_str(kline.datetime)
        log_str = ('{} {} <做多> 满足3小时 K线时间:{} MACD:{}')
        is_match = False
        if macd > 0:
            content = log_str.format(trade_time, s, kline_time, macd)
            logger.info(content)
            self.bci.setHoursByKline(kline)
            is_match = True
        return is_match

    def _match_30mk_cond(self, is_predicted=False) -> bool:
        '''做多30分钟线检测
        '''
        logger = self.logger
        kline = self._getLastDayLastM30Kline(is_predicted)
        utils = self._utils
        s = utils.tsi.current_symbol
        e5, e20, e60, macd, close, open_p, trade_time =\
            self.get_Kline_values(kline)
        kline_time = get_date_str(kline.datetime)
        log_str = ('{} {} <做多> 30分钟条件 K线时间:{} ema5:{} ema20:{} '
                   'ema60:{} 收盘:{} MACD:{}')
        is_match = False
        if close > e60 and e5 > e60:
            if self._is_within_distance(kline, self._is_long_macd_match):
                is_match = True
                self.bci.setMinutesCByKline(kline)
                content = log_str.format(
                    trade_time, s, kline_time, e5, e20, e60, close, macd)
                logger.info(content)
        return is_match

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
