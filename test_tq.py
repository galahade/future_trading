from datetime import date, datetime, timedelta, timezone

from tqsdk import TqApi, TqAuth, tafunc
from tqsdk.tafunc import time_to_datetime


def get_china_date_from_dt(dt: datetime) -> datetime:
    # 设置为UTC+8:00
    return dt.astimezone(timezone(timedelta(hours=8)))


api = TqApi(auth=TqAuth("galahade", "211212"))

d_klines = api.get_kline_serial("KQ.m@SHFE.ru", 60 * 60 * 24)
h3_klines = api.get_kline_serial("KQ.m@SHFE.ru", 60 * 60 * 3)
# print(klines["datetime"])
# klines["datetime1"] = klines["datetime"].apply(
#     lambda x: time_to_datetime(x).astimezone(timezone(timedelta(hours=8)))
# )
# klines["datetime1"] = klines["datetime"].apply(lambda x: time_to_datetime(x))
last_trade_date = get_china_date_from_dt(
    time_to_datetime(d_klines.iloc[-2].datetime)
)
print(last_trade_date)
h3k_time = last_trade_date.replace(hour=12)
l_timestamp = tafunc.time_to_ns_timestamp(h3k_time)
h3_kline = h3_klines[h3_klines.datetime <= l_timestamp].iloc[-1]
print(time_to_datetime(h3_kline.datetime))
print(get_china_date_from_dt(time_to_datetime(h3_kline.datetime)))
print(h3_kline)
api.close()
