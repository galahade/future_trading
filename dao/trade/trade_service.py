from tqsdk.objs import Order
from dao.odm.future_trade import (
    BottomCloseVolume, BottomOpenVolume, MJSBottomStatus, BottomOpenVolumeTip,
    BottomTradeStatus, MJSMainStatus, MainOpenVolume, MainCloseVolume,
    MainTradeStatus, MainJointSymbolStatus
)
import dao.trade.trade_dao as dao
import dao.trade.main_trade_dao as mdao
import dao.trade.bottom_trade_dao as bdao
from utils.common_tools import get_china_date_from_str, get_custom_symbol

from utils.tqsdk_tools import get_chinadt_from_ns


def get_main_sts(
        mj_symbol: str, current_symbol: str, next_symbol: str, direction: int,
        quote_date: str, strategy_name: str) -> MJSMainStatus:
    '''根据主连合约获取策略交易状态，如果不存在则在数据库中创建
    '''
    custom_symbol = get_custom_symbol(mj_symbol, direction, strategy_name)
    sts = mdao.getStrategyTradeStatus(custom_symbol)
    if sts is None:
        sts = mdao.createStrategyTradeStatus(
            mj_symbol, current_symbol, next_symbol, direction,
            get_china_date_from_str(quote_date))
    return sts


def get_bottom_sts(
        mj_symbol: str, current_symbol: str, next_symbol: str, direction: int,
        quote_date: str, strategy_name: str) -> MJSBottomStatus:
    '''根据主连合约获取交易状态信息，如果不存在则在数据库中创建
    '''
    custom_symbol = get_custom_symbol(mj_symbol, direction, strategy_name)
    sts = bdao.getStrategyTradeStatus(custom_symbol)
    if sts is None:
        sts = bdao.createStrategyTradeStatus(
            mj_symbol, current_symbol, next_symbol, direction,
            get_china_date_from_str(quote_date))
    return sts


def get_main_ov(symbol: str, direction: int) -> MainOpenVolume:
    '''根据主连合约代码,合约代码,交易方向 返回数据库中该合约的开仓信息
    '''
    return mdao.getOpenVolume(symbol, direction)


def get_bottom_ov(symbol: str, direction: int) -> BottomOpenVolume:
    '''根据主连合约代码,合约代码,交易方向 返回数据库中该合约的开仓信息
    '''
    return bdao.getOpenVolume(symbol, direction)


def main_open_pos_operation(
        status: MainTradeStatus, order: Order) -> MainOpenVolume:
    '''将开仓信息保存至数据库，并更新合约交易状态信息
    '''
    return mdao.saveOpenVolume(
        status, _get_odict_from_order(order))


def bottom_open_pos_operation(
        status: BottomTradeStatus, order: Order) -> BottomOpenVolume:
    '''将开仓信息保存至数据库，并更新合约交易状态信息
    '''
    return bdao.saveOpenVolume(
        status, _get_odict_from_order(order))


def main_close_pos_operation(
        status: MainTradeStatus, order: Order, c_type: str, c_message: str
        ) -> MainCloseVolume:
    '''将平仓信息保存至数据库，并更新合约交易状态信息
    '''
    c_dict = _get_cdict_from_order(order, c_type, c_message)
    return mdao.closePosAndUpdateStatus(status, c_dict)


def bottom_close_pos_operation(
        status: BottomTradeStatus, order: Order, c_type: str, c_message: str
        ) -> BottomCloseVolume:
    '''将平仓信息保存至数据库，并更新合约交易状态信息
    '''
    c_dict = _get_cdict_from_order(order, c_type, c_message)
    return bdao.closePosAndUpdateStatus(status, c_dict)


def switch_symbol(
        status: MainJointSymbolStatus, n_symbol: str, quote_time: str,
        order: Order) -> MainJointSymbolStatus:
    '''重置合约交易状态信息, 将合约变更至当前主力合约, 如果当前合约有持仓，则将其平仓'''
    dt = get_china_date_from_str(quote_time)
    n_sts = None
    if order is not None:
        if isinstance(status, MJSMainStatus):
            main_close_pos_operation(status, order, 2, '换月')
        elif isinstance(status, MJSBottomStatus):
            bottom_close_pos_operation(status, order, 2, '换月')
    if isinstance(status, MJSMainStatus):
        n_sts = mdao.createSymbolTradeStatus(
            status.custom_symbol, n_symbol, status.direction, dt)
    elif isinstance(status, MJSBottomStatus):
        n_sts = bdao.createSymbolTradeStatus(
            status.custom_symbol, n_symbol, status.direction, dt)
    return dao.set_switch_symbol_data(status, n_symbol, n_sts, dt)


def close_pos(status: MainJointSymbolStatus, c_type: int,
              c_message: str, order: Order) -> MainJointSymbolStatus:
    '''平仓，将合约交易状态信息重置为初始状态'''
    if isinstance(status, MJSMainStatus):
        main_close_pos_operation(status, order, c_type, c_message)
    elif isinstance(status, MJSBottomStatus):
        bottom_close_pos_operation(status, order, c_type, c_message)


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
