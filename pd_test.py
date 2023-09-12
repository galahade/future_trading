import pandas as pd
from tqsdk import TqApi, TqAuth, tafunc

# print(pd.__version__)  # '1.2.4'
# print(pd.Series().dtype)  # dtype('float64') --> dtype('object') in the future
api = TqApi(auth=TqAuth("galahade", "211212"))

d_klines = api.get_kline_serial("KQ.m@SHFE.ru", 60 * 60 * 24)
print(d_klines)
d_klines["column"] = pd.Series(dtype=pd.BooleanDtype())
# print(d_klines.loc[199, "column"])
print(pd.isna(d_klines.loc[199, "column"]))
d_klines.loc[199, "column"] = False

print(d_klines)

api.close()
