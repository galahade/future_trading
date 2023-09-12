from datetime import date

from dao.odm.trade_log import TradeRecord
from utils.common_tools import get_china_tz_now


def get_trade_record(day: date):
    """获取制定日期的交易日志"""
    return TradeRecord.objects(trade_date=day).first()


def create_trade_record(day: date) -> TradeRecord:
    """创建交易日志记录"""
    tr = TradeRecord()
    tr.trade_date = day
    tr.start_time = get_china_tz_now()
    tr.config_mj_symbols = []
    tr.involved_main_symbols = []
    tr.bottom_open_symbols = []
    tr.save()
    return tr


def finish(tr: TradeRecord):
    tr.end_time = get_china_tz_now()
    tr.has_run_pre_opt = True
    tr.has_trade = True
    tr.has_run_post_opt = True
    tr.save()
