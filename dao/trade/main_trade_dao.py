from datetime import datetime

from pandas import DataFrame

from dao.odm.future_trade import (
    MainCloseVolume, MainIndicatorValues, MainOpenCondition,
    MainOpenVolume, MainTradeStatus)
from dao.trade.trade_dao import save_close_volume, save_open_volume
from utils.common_tools import (
    get_china_date_from_dt, get_china_tz_now
)


def getTradeStatus(symbol: str, direction: int) -> MainTradeStatus:
    '''根据自定义合约代码获取交易状态信息'''
    return MainTradeStatus.objects(symbol=symbol, direction=direction).first()


def createTradeStatus(
        custom_symbol: str, symbol: str, direction: int, dt: datetime
) -> MainTradeStatus:
    ts = MainTradeStatus()
    ts.custom_symbol = custom_symbol
    ts.symbol = symbol
    ts.direction = direction
    ts.last_modified = dt
    ts.save()
    return ts


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
