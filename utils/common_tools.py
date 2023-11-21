import logging
import re
from datetime import date, datetime, timedelta, timezone

import requests
import yaml
from pypushdeer import PushDeer

from utils import global_var as gvar

pushdeer = PushDeer(pushkey=gvar.PUSH_KEY)
tz_utc_8 = timezone(timedelta(hours=8))  # 创建时区UTC+8:00，即东八区对应的时区
logger = logging.getLogger(__name__)


def sendPushDeerMsg(title: str, content: str):
    try:
        pushdeer.send_markdown(title, desp=content)
    except Exception as e:
        logger.exception(e)


def sendSystemStartupMsg(
    s_time: datetime, direction: int, strategy_ids: list[int]
):
    title = f'### {s_time.strftime("%Y-%m-%d")} {gvar.ENV_NAME}环境启动'
    strategies = ""
    for i in strategy_ids:
        if i == 1:
            strategies += "主策略 "
        elif i == 2:
            strategies += "摸底策略"
    direction_str = ""
    if direction == 1:
        direction_str = "做多"
    elif direction == 2:
        direction_str = "多空"
    elif direction == 0:
        direction_str = "做空"
    content = f'使用策略: **{strategies}**, 交易方向: **{direction_str}**, 启动时间: **{s_time.strftime("%Y-%m-%d %H:%M:%S")}**'
    sendPushDeerMsg(title, content)


def send_msg(title: str, content: str) -> None:
    """使用 Server Chan 发送相关消息。
    参考地址：https://sct.ftqq.com/after
    """
    logger = LoggerGetter()
    send_key = "SCT172591Tn14G9JYc890AUJyvsNUiuCcL"
    url = f"https://sctapi.ftqq.com/{send_key}.send"
    headers = {"content-type": "application/x-www-form-urlencoded"}
    data = {"title": title, "channel": 9, "desp": content}
    try:
        requests.post(url, data=data, headers=headers, timeout=10)
    except requests.RequestException as e:
        logger.exception(e)


def get_custom_symbol(zl_symbol: str, l_or_s: bool, s_name: str) -> str:
    symbol_list = examine_symbol(zl_symbol)
    return f'{symbol_list[1]}_{symbol_list[2]}_{s_name}_{"long" if l_or_s else "short"}'


def examine_symbol(_symbol) -> list[str]:
    pattern_dict_normal = {
        "CFFEX": re.compile(r"^(CFFEX).([A-Z]{1,2})(\d{4})$"),
        "CZCE": re.compile(r"^(CZCE).([A-Z]{2})(\d{3})$"),
        "DCE": re.compile(r"^(DCE).([a-z]{1,2})(\d{4})$"),
        "INE": re.compile(r"^(INE).([a-z]{2})(\d{4})$"),
        "SHFE": re.compile(r"^(SHFE).([a-z]{2})(\d{4})$"),
        "GFEX": re.compile(r"^(GFEX).([a-z]{2})(\d{4})$"),
        "KQ.m": re.compile(
            r"^(KQ.m@)(CFFEX|CZCE|DCE|INE|SHFE|GFEX).(\w{1,2})$"
        ),
    }

    for _, ipattern in pattern_dict_normal.items():
        matchsymbol = ipattern.match(_symbol)
        if matchsymbol:
            exchange, variety, expiry_month = (
                matchsymbol.group(1),
                matchsymbol.group(2),
                matchsymbol.group(3),
            )
            return [exchange, variety, expiry_month]
    raise ValueError(f"Invalid symbol: {_symbol}")


def get_zl_symbol(symbol: str) -> str:
    symbol_list = examine_symbol(symbol)
    return f"KQ.m@{symbol_list[0]}.{symbol_list[1]}"


def get_year_month_from_symbol(symbol_last_part):
    """从symbol中获取年月"""
    temp = int(symbol_last_part)
    year = int(temp / 100)
    month = temp % 100
    return year, month


def get_next_symbol(symbol: str, month_list: list[int]) -> str:
    """获取下一个合约"""
    symbol_list = examine_symbol(symbol)
    year, month = get_year_month_from_symbol(symbol_list[2])
    if len(symbol_list[2]) == 3:
        year_limit = 10
    else:
        year_limit = 100
    for i in range(len(month_list)):
        if month == month_list[i]:
            if i == len(month_list) - 1:
                month = month_list[0]
                year = (year + 1) % year_limit
            else:
                month = month_list[i + 1]
            break
    return f"{symbol_list[0]}.{symbol_list[1]}{year}{month:02d}"


def get_yaml_config(path: str | None) -> dict:
    if path is not None:
        with open(path, "r", encoding="UTF-8") as f:
            return yaml.safe_load(f.read())
    raise ValueError("Cant load yaml date from None path")


def get_date_from_symbol(symbol_last_part):
    temp = int(symbol_last_part)
    year = int(temp / 100) + 2000
    month = temp % 100
    day = 1
    return datetime(year, month, day, 0, 0, 0)


def get_china_tz_now() -> datetime:
    """获取当前时间，时区为东八区"""
    now = datetime.now()  # 默认构建的时间无时区
    return now.astimezone(tz_utc_8)  # 设置为UTC+8:00


def get_china_date_from_str(date_str: str) -> datetime:
    """将格式为2017-07-26 23:04:21.000001的字符串转换成 datetime 类型，
    该时间本身就是东八区的时间
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")  # 默认构建的时间无时区
    return dt


def get_china_date_from_dt(dt: datetime) -> datetime:
    # 设置为UTC+8:00
    return dt.astimezone(tz_utc_8)


def get_trade_date(trade_time: datetime) -> date:
    """根据传入的时间，获取交易日期
    由于天勤量化每天19:00断开服务，所以以19:00作为交易日的分界线。
    早于19:00则处在当日交易中，否则就进入下一交易日"""
    if trade_time.hour < 19:
        return trade_time.date()
    else:
        return (trade_time + timedelta(days=1)).date()


def run_nothing() -> bool:
    """根据当前时间判断目前所处时段是否处于不需要执行盘前操作时段。
    目前不需要操作的阶段为: 15:00 - 19:15
    盘前操作时段为: 每日19:15以后"""
    now = datetime.now(tz_utc_8)
    hour = now.hour
    minutes = now.minute
    if _is_weekend(now):
        return True
    else:
        if (hour >= 15 and hour < 19) or (hour == 19 and minutes < 15):
            return True
        return False


def dont_trading() -> bool:
    """根据当前时间判断目前所处时段是否需要执行交易
    不执行交易的时间段为: 15:00 - 20:45
    开始监控交易时间段为: 每日20:45以后"""
    now = datetime.now(tz_utc_8)
    hour = now.hour
    minutes = now.minute
    if _is_weekend(now):
        return True
    else:
        if (hour >= 15 and hour < 20) or (hour == 20 and minutes < 45):
            return True
        return False


def _is_weekend(date: datetime) -> bool:
    if date.isoweekday() in (6, 7):
        return True
    return False


class LoggerGetter:
    def __get__(self, obj, objtype=None) -> logging.Logger:
        return logging.getLogger(obj.__class__.__name__)
