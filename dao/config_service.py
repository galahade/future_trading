from utils.config_utils import FutureConfig, SystemConfig
import dao.odm.trade_config as odm_sc
import dao.odm.future_config as odm_fc
import dao.config_dao as dao


def get_system_config(config: SystemConfig) -> odm_sc.TradeConfigInfo:
    '''从数据库中读取系统配置信息，如果没有则根据配置文件内容创建
    '''
    sc_odm = dao.get_sc_odm()
    if sc_odm is None:
        sc_odm = dao.create_sc_odm(config)
    return sc_odm


def get_future_configs(configs: list[FutureConfig], is_backtest=False
                       ) -> list[odm_fc.FutureConfigInfo]:
    '''获取期货交易品种的配置信息
    回测时，期货交易信息从配置文件中取得。
    当正常交易时，期货交易信息先从数据库中读取期货配置信息， 如没有则从配置文件内容创建
    '''
    if is_backtest:
        fc_odms = dao.craeate_fc_odm(configs)
    else:
        fc_odms = dao.get_fc_odms()
        if len(fc_odms) == 0:
            fc_odms = dao.craeate_fc_odm(configs)
    return fc_odms
