from datetime import datetime
import hashlib
from pandas import DataFrame
from dao.trade.trade_dao import save_close_volume, save_open_volume
from dao.odm.future_trade import (
    BottomCloseVolume, BottomIndicatorValues, BottomOpenCondition,
    BottomOpenVolume, BottomOpenVolumeTip,
    BottomTradeStatus
)
from utils.common_tools import (
    get_china_date_from_dt, get_china_tz_now, get_custom_symbol
)


def getTradeStatus(symbol: str, direction: int) -> BottomTradeStatus:
    '''根据自定义合约代码获取交易状态信息'''
    return BottomTradeStatus.objects(
        symbol=symbol, direction=direction).first()


def createTradeStatus(
        mj_symbol: str, symbol: str, direction: int, dt: datetime
) -> BottomTradeStatus:
    sts = BottomTradeStatus()
    sts.custom_symbol = get_custom_symbol(mj_symbol, direction, 'bottom')
    sts.symbol = symbol
    sts.direction = direction
    sts.last_modified = dt
    sts.save()
    return sts


def getOpenVolume(symbol: str, direction: int) -> BottomOpenVolume:
    '''根据主连合约代码,合约代码，交易方向返回数据库中该合约的开仓信息'''
    return BottomOpenVolume.objects(symbol=symbol, direction=direction).first()


def openPosAndUpdateStatus(ts: BottomTradeStatus, opd: dict
                           ) -> BottomOpenVolume:
    '''保存开仓信息,并更新SymbolStatus中的持仓数量等信息'''
    ov = BottomOpenVolume()
    save_open_volume(ts, opd, ov)
    return ov


def closePosAndUpdateStatus(ts: BottomTradeStatus, cpd: dict
                            ) -> BottomCloseVolume:
    '''保存平仓信息,并更新SymbolStatus中的持仓数量等信息'''
    cv = BottomCloseVolume()
    save_close_volume(ts, cpd, cv)
    return cv


def createOpenVolumeTip(ts: BottomTradeStatus, ovtd: dict
                        ) -> BottomOpenVolumeTip:
    '''保存开仓提示信息,如果已存在则不作处理'''
    key = (ts.custom_symbol + ts.symbol
           + ovtd['kline_time'].strftime("%Y-%m-%d")
           )
    key_hash = hashlib.sha1(key.encode()).hexdigest()
    return BottomOpenVolumeTip.objects(_id=key_hash).update_one(
        custom_symbol=ts.custom_symbol, symbol=ts.symbol,
        dkline_time=get_china_date_from_dt(ovtd['d_kline'].datetime),
        direction=ts.direction, last_price=ovtd['d_kline'].close,
        volume=ovtd['volume'], last_modified=get_china_tz_now(),
        open_connection=createOpenConditon(ovtd), upsert=True)


def createOpenConditon(ocd: dict) -> BottomOpenCondition:
    boc = BottomOpenCondition()
    _d_c = BottomIndicatorValues()
    _3h_c = BottomIndicatorValues()
    _30m_c = BottomIndicatorValues()
    boc.daily_condition = _d_c
    boc.hourly_condition = _3h_c
    boc.minute_30_condition = _30m_c
    _fill_ivalues(ocd['d_kline'], _d_c)
    _fill_ivalues(ocd['3h_kline'], _3h_c)
    _fill_ivalues(ocd['30m_kline'], _30m_c)
    return boc


def switch_symbol(ts: BottomTradeStatus, n_symbol: str, dt: datetime):
    '''重置交易状态信息'''
    ts.switch_symbol(n_symbol, dt)
    ts.save()


def _fill_ivalues(kline: DataFrame, i_values: BottomIndicatorValues):
    i_values.ema5 = kline.ema5
    i_values.ema20 = kline.ema20
    i_values.ema60 = kline.ema60
    i_values.macd = kline['MACD.close']
    i_values.close = kline.close
    i_values.kline_time = get_china_date_from_dt(kline.datetime)
    i_values.record_time = get_china_tz_now()
