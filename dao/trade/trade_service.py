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


def get_MJStatus(
        mj_symbol: str, current_symbol: str, next_symbol: str, direction: int,
        quote_date: str, strategy_name: str) -> MainJointSymbolStatus:
    '''根据主连合约获取策略交易状态，如果不存在则在数据库中创建
    '''
    custom_symbol = get_custom_symbol(mj_symbol, direction, strategy_name)
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


def get_main_ov(symbol: str, direction: int) -> MainOpenVolume:
    '''根据主连合约代码,合约代码,交易方向 返回数据库中该合约的开仓信息
    '''
    return mdao.getOpenVolume(symbol, direction)


def get_bottom_ov(symbol: str, direction: int) -> BottomOpenVolume:
    '''根据主连合约代码,合约代码,交易方向 返回数据库中该合约的开仓信息
    '''
    return bdao.getOpenVolume(symbol, direction)


def open_pos(
        status: TradeStatus, order: Order) -> BottomOpenVolume:
    '''将开仓信息保存至数据库，并更新合约交易状态信息
    '''
    o_dict = _get_odict_from_order(order)
    if isinstance(status, MainTradeStatus):
        return mdao.openPosAndUpdateStatus(status, o_dict)
    elif isinstance(status, BottomTradeStatus):
        return bdao.openPosAndUpdateStatus(status, o_dict)


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
        status: BottomTradeStatus, ovtd: dict) -> BottomOpenVolumeTip:
    '''将开仓信息保存至数据库，并更新合约交易状态信息
    '''
    return bdao.createOpenVolumeTip(status, ovtd)
