import hashlib
from datetime import datetime
from typing import List

import dao.trade.trade_dao as dao
from dao.odm.future_trade import (
    BottomCloseVolume,
    BottomOpenCondition,
    BottomOpenVolume,
    BottomOpenVolumeTip,
    BottomTradeStatus,
    MainJointSymbolStatus,
    TradeStatus,
)
from utils.common_tools import get_china_date_from_dt, get_china_tz_now


def getBottomOpenVolumeTips() -> List[BottomOpenVolumeTip]:
    return BottomOpenVolumeTip.objects()


def getTradeStatus(symbol: str, direction: int) -> BottomTradeStatus:
    """根据自定义合约代码获取交易状态信息"""
    return BottomTradeStatus.objects(
        symbol=symbol, direction=direction
    ).first()


def getTradeStatusByCustomSymbol(
    custom_symbol: str,
) -> list[BottomTradeStatus]:
    """根据自定义合约代码获取交易状态信息"""
    return BottomTradeStatus.objects(custom_symbol=custom_symbol)


def createTradeStatus(
    custom_symbol: str, symbol: str, direction: int, dt: datetime
) -> BottomTradeStatus:
    ts = BottomTradeStatus()
    ts.custom_symbol = custom_symbol
    ts.symbol = symbol
    ts.direction = direction
    ts.last_modified = dt
    ts.save()
    return ts


def getOpenVolume(symbol: str, direction: int) -> BottomOpenVolume:
    """根据主连合约代码,合约代码，交易方向返回数据库中该合约的开仓信息"""
    return BottomOpenVolume.objects(symbol=symbol, direction=direction).first()


def openPosAndUpdateStatus(
    ts: BottomTradeStatus, opd: dict, bovt: BottomOpenVolumeTip
) -> BottomOpenVolume:
    """保存开仓信息,并更新SymbolStatus中的持仓数量等信息"""
    ov = BottomOpenVolume()
    ov.tip = bovt
    dao.save_open_volume(ts, opd, ov)
    return ov


def closePosAndUpdateStatus(
    ts: BottomTradeStatus, cpd: dict
) -> BottomCloseVolume:
    """保存平仓信息,并更新SymbolStatus中的持仓数量等信息"""
    cv = BottomCloseVolume()
    dao.save_close_volume(ts, cpd, cv)
    return cv


def createOpenVolumeTip(
    ts: BottomTradeStatus, open_condition: BottomOpenCondition, pos: int
) -> BottomOpenVolumeTip:
    """保存开仓提示信息,如果已存在则不作处理"""
    dc = open_condition.daily_condition
    key = ts.custom_symbol + ts.symbol + dc.kline_time.strftime("%Y-%m-%d")
    key_hash = hashlib.sha1(key.encode()).hexdigest()
    return BottomOpenVolumeTip.objects(id=key_hash).update_one(
        upsert=True,
        set_on_insert__id=key_hash,
        set_on_insert__custom_symbol=ts.custom_symbol,
        set_on_insert__symbol=ts.symbol,
        set_on_insert__dkline_time=get_china_date_from_dt(dc.kline_time),
        set_on_insert__direction=ts.direction,
        set_on_insert__last_price=dc.close,
        set_on_insert__need_trade=False,
        set__volume=pos,
        set__last_modified=get_china_tz_now(),
        set_on_insert__open_condition=open_condition,
    )


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
