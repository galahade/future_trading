from datetime import datetime
from dao.odm.future_trade import (
    BottomOpenVolume, MainJointSymbolStatus, TradeStatus
)
import dao.trade.main_trade_dao as mdao
import dao.trade.bottom_trade_dao as bdao


def save_close_volume(ts: TradeStatus, cpd: dict, cv):
    '''主策略和摸底策略共用方法，用来保存'''
    opi = ts.open_pos_info
    cv.symbol = opi.symbol
    cv.direction = opi.direction
    cv.trade_price = cpd['trade_price']
    cv.volume = cpd['volume']
    cv.trade_time = cpd['trade_time']
    cv.order_id = cpd['order_id']
    cv.last_modified = cpd['trade_time']
    cv.close_type = cpd['close_type']
    cv.close_message = cpd['close_message']
    cv.save()
    opi.close_pos_infos.append(cv)
    ts.carrying_volume = ts.carrying_volume - cv.volume
    if ts.carrying_volume == 0:
        ts.trade_status = 2
        ts.end_time = cv.trade_time
    ts.save(cascade=True)


def save_open_volume(ts: TradeStatus, opd: dict, ov):
    '''主策略和摸底策略共用方法，用来保存'''
    ov.symbol = ts.symbol
    ov.direction = ts.direction
    ov.trade_price = opd['trade_price']
    ov.volume = opd['volume']
    ov.trade_time = opd['trade_time']
    ov.order_id = opd['order_id']
    ov.last_modified = opd['trade_time']
    if isinstance(ov, BottomOpenVolume):
        ov.open_condition = bdao.createOpenConditon(opd)
    else:
        ov.open_condition = mdao.createOpenConditon(opd)
    ov.save()
    ts.trade_status = 1
    ts.carrying_volume = ov.volume
    ts.start_time = ov.trade_time
    ts.open_pos_info = ov
    ts.save(cascade=True)


def switchSymbol(sts: MainJointSymbolStatus, symbol: str,
                 t_time: datetime) -> MainJointSymbolStatus:
    '''重置期货合约交易状态信息'''
    sts.switch_symbol(symbol, t_time)
    sts.save()
    return sts


def closeout(sts: TradeStatus, symbol: str, t_time: datetime
             ) -> TradeStatus:
    '''平仓'''
    sts.closeout(symbol, t_time)
    sts.save()
    return sts


def set_switch_symbol_data(
    sdss: MainJointSymbolStatus, n_symbol: str, n_sts: TradeStatus,
        switch_time: datetime) -> MainJointSymbolStatus:
    '''重置期货合约交易状态信息'''
    sdss.switch_symbol(n_symbol, n_sts, switch_time)
    sdss.save()
    return sdss
