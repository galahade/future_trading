from datetime import date

import dao.trade_log.log_dao as dao
from dao.odm.trade_log import InvolvedSymbol, TradeRecord


def get_trade_record(day: date) -> TradeRecord:
    """ """
    tr = dao.get_trade_record(day)
    if tr is None:
        tr = dao.create_trade_record(day)
    return tr


def finish_trade_record(tr: TradeRecord):
    dao.finish(tr)


def add_config_mj_symbol(tr: TradeRecord, mj_symbol: str):
    tr.config_mj_symbols.append(mj_symbol)
    tr.save()


def add_involved_main_symbol(tr: TradeRecord, i_symbol: InvolvedSymbol):
    tr.involved_main_symbols.append(i_symbol)


def save_trade_record(tr: TradeRecord):
    tr.save()
