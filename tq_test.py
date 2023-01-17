from datetime import date
from tqsdk import TqApi, TqAuth, TqBacktest, BacktestFinished, tafunc
from utils.bottom_trade_tools import get_date_str
from datetime import datetime


def _getLastTradeDate() -> datetime:
    d_kline = klines.iloc[-2]
    dk_time = tafunc.time_to_datetime(d_kline.datetime)
    return datetime(dk_time.year, dk_time.month, dk_time.day)


def _getLastDayLastH3Kline():
    lastday_time = _getLastTradeDate()
    lastday_lasth3k_time = lastday_time.replace(hour=12)
    l_timestamp = tafunc.time_to_ns_timestamp(lastday_lasth3k_time)
    return h3_klines[h3_klines.datetime <= l_timestamp].iloc[-1]


def _getLastDayLastM30Kline():
    last_trade_date = _getLastTradeDate()
    lastday_lasth3k_time = last_trade_date.replace(hour=14, minute=30)
    l_timestamp = tafunc.time_to_ns_timestamp(lastday_lasth3k_time)
    return m30_klines[m30_klines.datetime <= l_timestamp].iloc[-1]


api = TqApi(backtest=TqBacktest(start_dt=date(2020, 1, 1),
                                end_dt=date(2020, 1, 5)),
            auth=TqAuth("galahade", "211212"))
quote = api.get_quote("KQ.m@DCE.i")
symbol = "SHFE.rb2005"
klines = api.get_kline_serial(symbol, 60*60*24)
h3_klines = api.get_kline_serial(symbol, 60*60*3)
m30_klines = api.get_kline_serial(symbol, 60*30)
try:
    while True:
        api.wait_update()
        if api.is_changing(klines.iloc[-1], "datetime"):
            l_h3_kline = _getLastDayLastH3Kline()
            l_m30_kline = _getLastDayLastM30Kline()
            print(l_m30_kline)
            l_d_time = get_date_str(klines.iloc[-2].datetime)
            l_h3_time = get_date_str(l_h3_kline.datetime)
            l_m30_time = get_date_str(l_m30_kline.datetime)
            print(f'last day time: {l_d_time}'
                  f'last day last 3h time: {l_h3_time}'
                  f'last 30m time: {l_m30_time}')
except BacktestFinished:
    api.close()
