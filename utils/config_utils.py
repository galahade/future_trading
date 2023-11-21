from typing import List

from utils import global_var as gvar
from utils.common_tools import get_yaml_config


class SystemConfig:
    """系统运行相关配置通过该类读取"""

    def __init__(self, **configs):
        self.__dict__.update(configs)
        self.mongo_config = CommonConfig(**self.db["mongo"])
        self.tq_config = CommonConfig(**self.accounts["tq"])
        self.trade_config = TradeConfig(**self.trade)


class CommonConfig:
    def __init__(self, **configs):
        self.__dict__.update(configs)


class TradeConfig:
    def __init__(self, **configs):
        self.__dict__.update(configs)
        self.start_date = self.backtest_days["start_date"]
        self.end_date = self.backtest_days["end_date"]


def get_system_config() -> SystemConfig:
    """从配置文件中读取系统配置信息

    系统配置信息包括: MongoDB数据库配置信息、期货交易账户配置信息、期货交易策略配置信息
    其中 MongoDB配置信息必须在配置文件中存在.
    其他配置信息优先在数据库中读取，如数据库中不存在则使用系统配置文件中的配置信息
    配置文件路径通过环境变量 `SYSTEM_CONFIG_PATH` 获得

    Returns:
        SystemConfig: 返回系统配置信息
    """
    return SystemConfig(**get_yaml_config(gvar.SYSTEM_CONFIG_PATH))


class FutureConfig:
    """期货交易品种配置信息"""

    def __init__(self, open_pos_scale, **config):
        self.__dict__.update(config)
        self.open_pos_scale = open_pos_scale
        self.long_trade_config = LongTradeConfig(**self.long)
        self.short_trade_config = ShortTradeConfig(**self.short)


class LongTradeConfig:
    """多头交易参数配置信息"""

    def __init__(self, **config):
        self.__dict__.update(config)


class ShortTradeConfig:
    """空头交易参数配置信息"""

    def __init__(self, **config):
        self.__dict__.update(config)


def get_future_configs() -> List[FutureConfig]:
    """从系统配置文件中读取期货交易品种配置信息"""
    configs = get_yaml_config(gvar.FUTURE_CONFIG_PATH)
    future_configs = configs["futures"]
    open_pos_scale = configs["open_pos_scale"]
    # use a array to store all the future configs
    return [
        FutureConfig(open_pos_scale, **future_config)
        for future_config in future_configs
    ]
