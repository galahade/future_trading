import re
from datetime import datetime, timedelta, timezone
import logging
import yaml
import requests
tz_utc_8 = timezone(timedelta(hours=8))  # 创建时区UTC+8:00，即东八区对应的时区 


def send_msg(title: str, content: str) -> None:
    ''' 使用 Server Chan 发送相关消息。
    参考地址：https://sct.ftqq.com/after
    '''
    logger = LoggerGetter()
    send_key = 'SCT172591Tn14G9JYc890AUJyvsNUiuCcL'
    url = f'https://sctapi.ftqq.com/{send_key}.send'
    headers = {"content-type": "application/x-www-form-urlencoded"}
    data = {'title': title, 'channel': 9, 'desp': content}
    try:
        requests.post(url, data=data, headers=headers, timeout=10)
    except requests.RequestException as e:
        logger.exception(e)


def get_custom_symbol(zl_symbol: str, l_or_s: bool, s_name: str) -> str:
    symbol_list = examine_symbol(zl_symbol)
    return f'{symbol_list[1]}_{symbol_list[2]}_{s_name}_{"long" if l_or_s else "short"}'


def examine_symbol(_symbol):
    pattern_dict_normal = {
        'CFFEX': re.compile(r'^(CFFEX).([A-Z]{1,2})(\d{4})$'),
        'CZCE': re.compile(r'^(CZCE).([A-Z]{2})(\d{3})$'),
        'DCE': re.compile(r'^(DCE).([a-z]{1,2})(\d{4})$'),
        'INE': re.compile(r'^(INE).([a-z]{2})(\d{4})$'),
        'SHFE': re.compile(r'^(SHFE).([a-z]{2})(\d{4})$'),
        'KQ.m': re.compile(r'^(KQ.m@)(CFFEX|CZCE|DCE|INE|SHFE).(\w{1,2})$')
        }

    for _, ipattern in pattern_dict_normal.items():
        matchsymbol = ipattern.match(_symbol)
        if matchsymbol:
            exchange, variety, expiry_month = \
                matchsymbol.group(1), matchsymbol.group(2), \
                matchsymbol.group(3)
            return [exchange, variety, expiry_month]
    return False


def get_zl_symbol(symbol: str) -> str:
    symbol_list = examine_symbol(symbol)
    return f'KQ.m@{symbol_list[0]}.{symbol_list[1]}'


def get_year_month_from_symbol(symbol_last_part):
    '''从symbol中获取年月'''
    temp = int(symbol_last_part)
    year = int(temp / 100)
    month = temp % 100
    return year, month


def get_next_symbol(symbol: str, month_list: list[int]) -> str:
    '''获取下一个合约'''
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
    return f'{symbol_list[0]}.{symbol_list[1]}{year}{month:02d}'


def get_yaml_config(path: str) -> dict:
    with open(path, 'r', encoding='UTF-8') as f:
        return yaml.safe_load(f.read())


def get_date_from_symbol(symbol_last_part):
    temp = int(symbol_last_part)
    year = int(temp / 100) + 2000
    month = temp % 100
    day = 1
    return datetime(year, month, day, 0, 0, 0)


def get_china_tz_now() -> datetime:
    '''获取当前时间，时区为东八区'''
    now = datetime.now()  # 默认构建的时间无时区 
    return now.astimezone(tz_utc_8)  # 设置为UTC+8:00


def get_china_date_from_str(date_str: str) -> datetime:
    '''将格式为2017-07-26 23:04:21.000001的字符串转换成 datetime 类型，时区为东八区'''
    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')  # 默认构建的时间无时区 
    return dt.astimezone(tz_utc_8)  # 设置为UTC+8:00


def get_china_date_from_dt(dt: datetime) -> datetime:
    return dt.astimezone(tz_utc_8)  # 设置为UTC+8:00


class LoggerGetter:
    def __get__(self, obj, objtype=None) -> logging.Logger:
        return logging.getLogger(obj.__class__.__name__)
