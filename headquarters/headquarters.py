import os
import uuid
from typing import Optional
from mongoengine import connect
# from tqsdk2 import TqRohon, TqAuth, TqSim
from pymongo import MongoClient
from tqsdk import TqApi, TqBacktest, TqAuth, TqSim
import dao.config_service as c_service
from dao.odm.trade_config import TradeConfigInfo
from strategies.trade_strategies.trade_strategies import (
    TradeStrategy)
from exe_departments.stakers import BTStaker, RealStaker
import utils.config_utils as c_utils
from utils.config_utils import (SystemConfig)
from utils.common_tools import tz_utc_8, LoggerGetter
# from tqsdk2 import TqApi, TqBacktest, BacktestFinished

ACCOUNT_BALANCE = int(os.getenv('ACCOUNT_BALANCE', '10000000'))


class Commander:
    '''期货交易总指挥，根据交易系统配置生成实盘/回测盯盘人，
    同时根据期货交易品种配置生成交易人，并为其配备合适的交易算法
    系统配置文件通过环境变量TRADE_CONFIG_PATH获得。
    '''
    def __init__(self):
        _config = c_utils.get_system_config()
        self.dba = DBA(_config)
        self.account_manager = AccountManager(
            c_service.get_system_config(_config))
        self.trade_manager = TradeManager(self.account_manager)

    def _connect_to_db(self, config: SystemConfig):
        '''连接MongoDB数据库, 现在还不确定是否需要持有 dba 角色，故暂时保留'''
        self.dba = DBA(config)


class DBA:
    '''使用系统配置文件中的MongoDB配置信息，连接MongoDB数据库
    '''
    db_client = Optional[MongoClient]

    def __init__(self, config: SystemConfig):
        mongo_config = config.mongo_config
        trade_config = config.trade_config
        host = mongo_config.host
        port = mongo_config.port
        if hasattr(mongo_config, 'user'):
            user = mongo_config.user
            password = mongo_config.password
            url = f'mongodb://{user}:{password}@{host}:{port}/'
        else:
            url = f'mongodb://{host}:{port}/'
        if trade_config.is_backtest:
            db_name = str(uuid.uuid4())
        else:
            db_name = 'future_trade'
        db_url = f'{url}{db_name}'
        connect(host=db_url, tz_aware=True, tzinfo=tz_utc_8)

    def getMDBbyName(self, name='future_trade'):
        return self.db_client.get_database(name)


class AccountManager:
    def __init__(self, trade_config: TradeConfigInfo):
        self.trade_config = trade_config
        # rohon_config = sc_odm.rohon_config()
        _tq_acc = trade_config.tq_account
        self._acc_type = trade_config.account_type
        if self._acc_type == 1:
            self.trade_account = None
        elif self._acc_type == 2:
            self.trade_account = None
            # self._trade_account = TqRohon(td_url, broker_id, app_id,
            # auth_code, # user_name, password)
        else:
            self.trade_account = TqSim(init_balance=ACCOUNT_BALANCE)
        self.tq_auth = TqAuth(_tq_acc.user_name, _tq_acc.password)

    def is_real_account(self):
        return bool(self._acc_type)


class TradeManager:
    logger = LoggerGetter()

    def __init__(self, acc_manager: AccountManager):
        self.trade_config = acc_manager.trade_config
        self.is_backtest = self.trade_config.is_backtest
        self.direction = self.trade_config.direction
        trade_account = acc_manager.trade_account
        self.strategies = self._get_trade_strategies(
            self.trade_config.strategies
        )
        if self.is_backtest:
            self.logger.info('使用回测模式')
            self.tqApi = TqApi(
                account=trade_account, auth=acc_manager.tq_auth,
                backtest=TqBacktest(
                    start_dt=self.trade_config.backtest_days.start_date,
                    end_dt=self.trade_config.backtest_days.end_date))
            self.staker = BTStaker(
                self.tqApi, self.strategies, self.direction)
        else:
            self.logger.info('使用实盘模式')
            if acc_manager.is_real_account():
                self.logger.info('使用实盘账户进行交易')
            else:
                self.logger.info('使用模拟账户进行交易')
            self.tqApi = TqApi(account=trade_account, auth=acc_manager.tq_auth)
            self.staker = RealStaker(
                self.tqApi, self.strategies, self.direction)

    def _get_trade_strategies(self, strategy_ids: list(int)) -> list(TradeStrategy):
        strategies = []
        for strategy_id in strategy_ids:
            if strategy_id == 1:
                strategies.append(MainStrategy())
                self.logger.info('主策略被启用')
            elif strategy_id == 2:
                strategies.append(BottomLongSymbolsStrategy())
                self.logger.info('摸底策略被启用')
        return strategies
    
    def start_working(self):
        logger = self.logger
        logger.info('交易准备开始')
        logger.debug(f'交易初始资金为{self.tqApi.get_account().balance}')
        ftu_list = [BottomTradeBrokerManager(
            api, fc, self.direction, just_check, self.service, is_backtest)
                    for fc in self.service.get_future_configs()]
        active_ftu_list = [BottomTradeBrokerManager(
            api, fc, self.direction, just_check, self.service, is_backtest)
                    for fc in self.service.get_active_future_configs()]
        logger.debug("准备开始摸底策略交易.")
        [ftu.before_open_operation() for ftu in ftu_list]
        logger.info('当前参与交易品种为:')
        for ftu in active_ftu_list:
            logger.info(f'{ftu._zl_symbol}')
        api.wait_update()
        logger.debug("天勤服务器端已更新，开始实盘交易日工作")
        while True:
            api.wait_update()
            for ftu in active_ftu_list:
                ftu.daily_opration()