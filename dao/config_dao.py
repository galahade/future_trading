from dao.odm.future_config import FutureConfigInfo, LongConfig, ShortConfig
from dao.odm.trade_config import Account, BacktestDays, TradeConfigInfo
from utils.common_tools import get_china_tz_now
from utils.config_utils import FutureConfig, SystemConfig


def get_sc_odm():
    """返回数据库中的系统配置信息"""
    return TradeConfigInfo.objects().first()


def create_sc_odm(config: SystemConfig) -> TradeConfigInfo:
    """根据配置文件内容创建系统配置信息并保存到数据库中"""
    sc_odm = TradeConfigInfo()
    t_config = config.trade_config
    tq_config = config.tq_config
    sc_odm.direction = t_config.direction
    sc_odm.is_backtest = t_config.is_backtest
    sc_odm.strategy_ids = t_config.strategies
    bd = BacktestDays()
    bd.start_date = t_config.start_date
    bd.end_date = t_config.end_date
    sc_odm.backtest_days = bd
    sc_odm.date_time = get_china_tz_now()
    tq_account = Account()
    tq_account.user_name = tq_config.user
    tq_account.password = tq_config.password
    sc_odm.tq_account = tq_account
    sc_odm.save()
    return sc_odm


def get_fc_odms() -> list[FutureConfigInfo]:
    return FutureConfigInfo.objects().order_by("symbol")


def craeate_fc_odm(configs: list[FutureConfig]) -> list[FutureConfigInfo]:
    for config in configs:
        long_config = LongConfig()
        ltc = config.long_trade_config
        long_config.base_scale = ltc.base_scale
        long_config.profit_start_scale_1 = ltc.profit_start_scale_1
        long_config.profit_start_scale_2 = ltc.profit_start_scale_2
        long_config.promote_scale_1 = ltc.promote_scale_1
        long_config.promote_scale_2 = ltc.promote_scale_2
        long_config.promote_target_1 = ltc.promote_target_1
        long_config.promote_target_2 = ltc.promote_target_2
        long_config.stop_loss_scale = ltc.stop_loss_scale
        short_config = ShortConfig()
        stc = config.short_trade_config
        short_config.base_scale = stc.base_scale
        short_config.profit_start_scale = stc.profit_start_scale
        short_config.promote_scale = stc.promote_scale
        short_config.promote_target = stc.promote_target
        short_config.stop_loss_scale = stc.stop_loss_scale
        FutureConfigInfo.objects(symbol=config.symbol).update_one(
            upsert=True,
            full_result=True,
            set_on_insert__symbol=config.symbol,
            set_on_insert__name=config.name,
            set__open_pos_scale=config.open_pos_scale,
            set__switch_days=config.switch_days,
            set__main_symbols=config.main_symbols,
            set__multiple=config.multiple,
            set__is_active=bool(config.is_active),
            set__long_config=long_config,
            set__short_config=short_config,
        )
    return get_fc_odms()
