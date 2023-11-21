import hashlib
from datetime import datetime

from pandas import DataFrame

import dao.trade.trade_dao as dao
from dao.odm.future_trade import (
    CloseCondition,
    MainCloseVolume,
    MainDailyConditionTip,
    MainIndicatorValues,
    MainJointSymbolStatus,
    MainOpenCondition,
    MainOpenVolume,
    MainTradeStatus,
    TradeStatus,
)
from utils.common_tools import get_china_date_from_dt, get_china_tz_now


def getTradeStatus(symbol: str, direction: int) -> MainTradeStatus:
    """根据自定义合约代码获取交易状态信息"""
    return MainTradeStatus.objects(symbol=symbol, direction=direction).first()


def getTradeStatusByCustomSymbol(custom_symbol: str) -> list[MainTradeStatus]:
    """根据自定义合约代码获取交易状态信息"""
    return MainTradeStatus.objects(custom_symbol=custom_symbol)


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
    """根据主连合约代码,合约代码，交易方向返回数据库中该合约的开仓信息"""
    return MainOpenVolume.objects(symbol=symbol, direction=direction).first()


def openPosAndUpdateStatus(
    ts: MainTradeStatus,
    o_condition: MainOpenCondition,
    c_condition: CloseCondition,
    opd: dict,
) -> MainOpenVolume:
    """保存开仓信息,并更新Main Symbol Trade Status 中的持仓数量等信息"""
    ov = MainOpenVolume()
    ov.open_condition = o_condition
    ov.close_condition = c_condition
    dao.save_open_volume(ts, opd, ov)
    return ov


def closePosAndUpdateStatus(ts: MainTradeStatus, cpd: dict) -> MainCloseVolume:
    """保存平仓信息,并更新SymbolStatus中的持仓数量等信息"""
    cv = MainCloseVolume()
    dao.save_close_volume(ts, cpd, cv)
    return cv


def createOpenConditon(ocd: dict) -> MainOpenCondition:
    boc = MainOpenCondition()
    _d_c = MainIndicatorValues()
    _3h_c = MainIndicatorValues()
    _30m_c = MainIndicatorValues()
    boc.daily_condition = _d_c
    boc.hourly_condition = _3h_c
    boc.minute_30_condition = _30m_c
    _fill_ivalues(ocd["d_kline"], _d_c)
    _fill_ivalues(ocd["3h_kline"], _3h_c)
    _fill_ivalues(ocd["30m_kline"], _30m_c)
    return boc


def _fill_ivalues(kline: DataFrame, i_values: MainIndicatorValues):
    i_values.ema9 = kline.ema9
    i_values.ema20 = kline.ema20
    i_values.ema60 = kline.ema60
    i_values.macd = kline["MACD.close"]
    i_values.close = kline.close
    i_values.open = kline.open
    i_values.kline_time = get_china_date_from_dt(kline.datetime)
    i_values.record_time = get_china_tz_now()


def switch_symbol(
    mj_status: MainJointSymbolStatus,
    current_status: TradeStatus,
    next_status: TradeStatus,
    new_status: TradeStatus,
):
    """重置期货合约交易状态信息, 用于下一个交易合约使用"""
    trade_status_list = getTradeStatusByCustomSymbol(mj_status.custom_symbol)
    dao.switch_symbol(
        mj_status, current_status, next_status, new_status, trade_status_list
    )


def createDailyConditionTip(
    ts: MainTradeStatus, open_condition: MainOpenCondition
) -> MainDailyConditionTip:
    """保存主策略日线条件满足提示,如果已存在则只更新最后修改时间"""
    dc = open_condition.daily_condition
    key = ts.custom_symbol + ts.symbol + dc.kline_time.strftime("%Y-%m-%d")
    key_hash = hashlib.sha1(key.encode()).hexdigest()
    return MainDailyConditionTip.objects(id=key_hash).update_one(
        upsert=True,
        set_on_insert__id=key_hash,
        set_on_insert__custom_symbol=ts.custom_symbol,
        set_on_insert__symbol=ts.symbol,
        set_on_insert__direction=ts.direction,
        set_on_insert__ema9=dc.ema9,
        set_on_insert__ema22=dc.ema22,
        set_on_insert__ema60=dc.ema60,
        set_on_insert__macd=dc.macd,
        set_on_insert__close=dc.close,
        set_on_insert__open=dc.open,
        set_on_insert__condition_id=dc.condition_id,
        set_on_insert__kline_time=get_china_date_from_dt(dc.kline_time),
        set__last_modified=get_china_tz_now(),
    )
