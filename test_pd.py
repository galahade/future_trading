import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, tafunc

# print(pd.Series().dtype)  # dtype('float64') --> dtype('object') in the future
api = TqApi(auth=TqAuth("galahade", "211212"))

klines = api.get_kline_serial("KQ.m@SHFE.ru", 1)
# klines["column"] = pd.Series(dtype=pd.BooleanDtype())
klines["column"] = pd.Series()
lk = klines.iloc[-1]
# print(pd.isna(klines.loc[199, "column"]))
print(lk.name)
klines.loc[lk.name, "column"] = False
print(klines["column"])
# klines.convert_dtypes()
# print(klines["column"])
i = 0
while i < 3:
    api.wait_update()
    if api.is_changing(klines.iloc[-1], "datetime"):
        # klines["column"] = pd.Series()
        klines.loc[199, "column"] = True
        print(klines)
        i += 1
api.close()


def has_set_k_attr(kline: pd.Series, attr_value: str):
    kline.get(attr_value) is not None and not (np.isnan(kline.get(attr_value)))
