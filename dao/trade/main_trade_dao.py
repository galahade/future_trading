from datetime import datetime

from pandas import DataFrame

from dao.odm.future_trade import (
    MainCloseVolume, MJSMainStatus, MainIndicatorValues, MainOpenCondition,
    MainOpenVolume, MainTradeStatus)
from dao.trade.trade_dao import save_close_volume, save_open_volume
from utils.common_tools import (
    get_china_date_from_dt, get_china_tz_now, get_custom_symbol
)


def getStrategyTradeStatus(custom_symbol: str) -> MJSMainStatus:
    '''根据主连合约代码返回数据库中该主连合约交易状态状态信息'''
    return MJSMainStatus.objects(custom_symbol=custom_symbol).first()


def createStrategyTradeStatus(
        mj_symbol: str, current_symbol: str, next_symbol: int, direction: int,
        dt: datetime) -> MJSMainStatus:
    '''根据传入参数创建主连合约摸底策略交易状态信息并保存到数据库中,
    参数 direction: 0:多头, 1:空头. '''
    sts = MJSMainStatus()
    sts.custom_symbol = get_custom_symbol(mj_symbol, direction, 'main')
    sts.main_joint_symbol = mj_symbol
    sts.current_symbol = current_symbol
    sts.next_symbol = next_symbol
    sts.direction = direction
    sts.current_ts = createSymbolTradeStatus(
        sts.custom_symbol, current_symbol, direction, dt)
    sts.next_ts = createSymbolTradeStatus(
        sts.custom_symbol, current_symbol, direction, dt)
    sts.last_modified = dt
    sts.save()
    return sts


def createSymbolTradeStatus(
        custom_symbol: str, symbol: str, direction: int, dt: datetime
) -> MainTradeStatus:
    sts = MainTradeStatus()
    sts.custom_symbol = custom_symbol
    sts.symbol = symbol
    sts.direction = direction
    sts.last_modified = dt
    sts.save()
    return sts


def getSTStatus(symbol: str, direction: int) -> MJSMainStatus:
    '''根据主连合约代码,合约代码，交易方向返回数据库中该合约交易状态状态信息'''
    return MJSMainStatus.objects(symbol=symbol, direction=direction).first()


def getOpenVolume(symbol: str, direction: int) -> MainOpenVolume:
    '''根据主连合约代码,合约代码，交易方向返回数据库中该合约的开仓信息'''
    return MainOpenVolume.objects(symbol=symbol, direction=direction).first()


def openPosAndUpdateStatus(ts: MainTradeStatus, opd: dict) -> MainOpenVolume:
    '''保存开仓信息,并更新Main Symbol Trade Status 中的持仓数量等信息'''
    ov = MainOpenVolume()
    save_open_volume(ts, opd, ov)
    return ov


def closePosAndUpdateStatus(ts: MainTradeStatus, cpd: dict) -> MainCloseVolume:
    '''保存平仓信息,并更新SymbolStatus中的持仓数量等信息'''
    cv = MainCloseVolume()
    save_close_volume(ts, cpd, cv)
    return cv


def createOpenConditon(ocd: dict) -> MainOpenCondition:
    boc = MainOpenCondition()
    _d_c = MainIndicatorValues()
    _3h_c = MainIndicatorValues()
    _30m_c = MainIndicatorValues()
    boc.daily_condition = _d_c
    boc.hourly_condition = _3h_c
    boc.minute_30_condition = _30m_c
    _fill_ivalues(ocd['d_kline'], _d_c)
    _fill_ivalues(ocd['3h_kline'], _3h_c)
    _fill_ivalues(ocd['30m_kline'], _30m_c)
    return boc


def _fill_ivalues(kline: DataFrame, i_values: MainIndicatorValues):
    i_values.ema9 = kline.ema9
    i_values.ema20 = kline.ema20
    i_values.ema60 = kline.ema60
    i_values.macd = kline['MACD.close']
    i_values.close = kline.close
    i_values.open = kline.open
    i_values.kline_time = get_china_date_from_dt(kline.datetime)
    i_values.record_time = get_china_tz_now()
