from datetime import datetime, timedelta
from typing import List, Optional
from tqsdk.objs import Order
from dao.odm.future_trade import (
    BottomOpenVolume, BottomOpenVolumeTip,
    BottomTradeStatus, MainOpenVolume,
    MainTradeStatus, MainJointSymbolStatus, TradeStatus
)
import dao.trade.trade_dao as dao
import dao.trade.main_trade_dao as mdao
import dao.trade.bottom_trade_dao as bdao
from utils.common_tools import get_china_date_from_str, get_custom_symbol

from utils.tqsdk_tools import get_chinadt_from_ns
from mongoengine.queryset.visitor import Q


def get_MJStatus(
        mj_symbol: str, current_symbol: str, next_symbol: str, direction: int,
        quote_date: str, strategy_name: str) -> MainJointSymbolStatus:
    '''根据主连合约获取策略交易状态，如果不存在则在数据库中创建
    '''
    custom_symbol = get_custom_symbol(
        mj_symbol, bool(direction), strategy_name)
    mjss = dao.getMainJointSymbolStatus(custom_symbol)
    if mjss is None:
        mjss = dao.createMainJointSymbolStatus(
            mj_symbol, current_symbol, next_symbol, direction, strategy_name,
            get_china_date_from_str(quote_date))
    return mjss


def get_main_trade_status(
        custom_symbol: str, symbol: str, direction: int, quote_date: str
) -> MainTradeStatus:
    ts = mdao.getTradeStatus(symbol, direction)
    if ts is None:
        dt = get_china_date_from_str(quote_date)
        ts = mdao.createTradeStatus(
            custom_symbol, symbol, direction, dt)
    return ts


def get_bottom_trade_status(
        custom_symbol: str, symbol: str, direction: int, quote_date: str
) -> BottomTradeStatus:
    ts = bdao.getTradeStatus(symbol, direction)
    if ts is None:
        dt = get_china_date_from_str(quote_date)
        ts = bdao.createTradeStatus(
            custom_symbol, symbol, direction, dt)
    return ts


def del_trade_status(ts: TradeStatus):
    dao.deleteTradeStatus(ts)


def get_main_ov(symbol: str, direction: int) -> MainOpenVolume:
    '''根据主连合约代码,合约代码,交易方向 返回数据库中该合约的开仓信息
    '''
    return mdao.getOpenVolume(symbol, direction)


def get_bottom_ov(symbol: str, direction: int) -> BottomOpenVolume:
    '''根据主连合约代码,合约代码,交易方向 返回数据库中该合约的开仓信息
    '''
    return bdao.getOpenVolume(symbol, direction)


def open_main_pos(status: TradeStatus, order: Order):
    '''将开仓信息保存至数据库，并更新合约交易状态信息
    '''
    o_dict = _get_odict_from_order(order)
    return mdao.openPosAndUpdateStatus(status, o_dict)  # type: ignore


def open_bottom_pos(status: TradeStatus, order: Order, bovt: BottomOpenVolumeTip):
    '''将开仓信息保存至数据库，并更新合约交易状态信息
    '''
    o_dict = _get_odict_from_order(order)
    return bdao.openPosAndUpdateStatus(status, o_dict, bovt)  # type: ignore


def close_ops(status: TradeStatus, c_type: int, c_message: str,
              order: Order):
    '''平仓，将合约交易状态信息重置为初始状态'''
    c_dict = _get_cdict_from_order(order, c_type, c_message)
    if isinstance(status, MainTradeStatus):
        return mdao.closePosAndUpdateStatus(status, c_dict)
    elif isinstance(status, BottomTradeStatus):
        return bdao.closePosAndUpdateStatus(status, c_dict)


def switch_symbol(
        status: TradeStatus, n_symbol: str, quote_time: str,
        order: Order) -> TradeStatus:
    '''重置合约交易状态信息, 将其合约变更至当前主力合约

    如果换月时产生平仓交易，则将其平仓信息记录至数据库'''
    dt = get_china_date_from_str(quote_time)
    if order is not None:
        close_ops(status, 2, '换月', order)
    return dao.switch_symbol(status, n_symbol, dt)


def _get_cdict_from_order(order: Order, c_type: int, c_message: str) -> dict:
    '''从order对象中获取交易信息
    '''
    return {
        'trade_price': order.trade_price,
        'volume': order.volume_orign,
        'trade_time': get_chinadt_from_ns(order.insert_date_time),
        'order_id': order.order_id,
        'close_type': c_type,
        'close_message': c_message
    }


def _get_odict_from_order(order: Order) -> dict:
    '''从order对象中获取交易信息
    '''
    return {
        'trade_price': order.trade_price,
        'volume': order.volume_orign,
        'trade_time': get_chinadt_from_ns(order.insert_date_time),
        'order_id': order.order_id
    }


def store_b_open_volume_tip(
        status: BottomTradeStatus, pos: int) -> BottomOpenVolumeTip:
    '''将开仓信息保存至数据库，并更新合约交易状态信息
    '''
    return bdao.createOpenVolumeTip(status, pos)


def update_trade_status(status: TradeStatus, update_time: datetime):
    '''更新合约交易状态信息
    '''
    status.last_modified = update_time
    dao.updateTradeStatus(status)


def get_last_bottom_tips() -> Optional[List[BottomOpenVolumeTip]]:
    '''获取最近的开仓提示信息
    '''
    return BottomOpenVolumeTip.get_last_tips()  # type: ignore


def get_last_bottom_tips_by_symbol(
        symbol: str, direction: int) -> Optional[BottomOpenVolumeTip]:
    queryset = None
    try:
        queryset = get_last_bottom_tips()
    except Exception:
        pass
    if queryset is not None:
        return queryset.filter(Q(symbol=symbol) & Q(direction=direction)).first() # type: ignore
    return None


def get_last7d_count(bovt: BottomOpenVolumeTip) -> int:
    '''获取最近7天的开仓提示数量
    '''
    return BottomOpenVolumeTip.objects(
        Q(symbol=bovt.symbol) & Q(direction=bovt.direction) &
        Q(dkline_time__gte=bovt.dkline_time - timedelta(days=7))
    ).count()  # type: ignore
