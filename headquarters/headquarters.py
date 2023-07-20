import os
from typing import Optional
import uuid
from mongoengine import connect
# from tqsdk2 import TqRohon, TqAuth, TqSim
from tqsdk import TqApi, TqBacktest, TqAuth, TqSim
import dao.config_service as c_service
from dao.odm.trade_config import TradeConfigInfo
from exe_departments.stakers import BTStaker, RealStaker
import utils.config_utils as c_utils
from utils.config_utils import (SystemConfig)
from utils.common_tools import tz_utc_8, LoggerGetter
# from tqsdk2 import TqApi, TqBacktest, BacktestFinished

ACCOUNT_BALANCE = int(os.getenv('ACCOUNT_BALANCE', '10000000'))


class Commander:
    '''期货交易总指挥，根据交易系统配置生成支持交易的各种角色，并协调完成交易工作

    交易角色包括：
        DBA：管理数据库连接。将对接好的数据库交给其他角色使用。
        AccountManager：管理交易账户。根据交易系统配置生成交易账户.
        TradeManager：交易主管。负责利用系统提供的资源开展交易工作。
    '''

    def __init__(self, is_backtest: bool):
        _config = c_utils.get_system_config(is_backtest)
        self._dba = DBA(_config)
        self._dba.create_db()
        self._account_manager = AccountManager(
            c_service.get_system_config(_config))
        self.trade_manager = TradeManager(self._account_manager)

    def start_work(self):
        '''交易的开端'''
        self.trade_manager.start_work()


class DBA:
    '''使用系统配置文件中的MongoDB配置信息，连接MongoDB数据库
    '''

    def __init__(self, config: SystemConfig):
        mongo_config = config.mongo_config
        self._trade_config = config.trade_config
        host = mongo_config.host  # type: ignore
        port = mongo_config.port  # type: ignore
        if hasattr(mongo_config, 'user'):
            user = mongo_config.user  # type: ignore
            password = mongo_config.password  # type: ignore
            self._url = f'mongodb://{user}:{password}@{host}:{port}/'
        else:
            self._url = f'mongodb://{host}:{port}/'

    def create_db(self, db_name: Optional[str] = None):
        if db_name is None:
            if self._trade_config.is_backtest:  # type: ignore
                db_name = str(uuid.uuid4())
            else:
                db_name = 'future_trade'
        db_url = f'{self._url}{db_name}?authSource=admin'
        connect(host=db_url, tz_aware=True, tzinfo=tz_utc_8)


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
        self.tq_auth = TqAuth(
            _tq_acc.user_name, _tq_acc.password)  # type: ignore

    def is_real_account(self):
        return bool(self._acc_type)


class TradeManager:
    logger = LoggerGetter()

    def __init__(self, acc_manager: AccountManager):
        trade_config = acc_manager.trade_config
        is_backtest = trade_config.is_backtest
        direction = trade_config.direction
        trade_account = acc_manager.trade_account
        if is_backtest:
            self.logger.info('使用回测模式')
            self.tqApi = TqApi(
                account=trade_account, auth=acc_manager.tq_auth,
                backtest=TqBacktest(
                    start_dt=trade_config.backtest_days.start_date,
                    end_dt=trade_config.backtest_days.end_date))
            self.staker = BTStaker(
                self.tqApi, direction, trade_config.strategy_ids)
        else:
            self.logger.info('使用实盘模式')
            if acc_manager.is_real_account():
                self.logger.info('使用实盘账户进行交易')
            else:
                self.logger.info('使用模拟账户进行交易')
            self.tqApi = TqApi(account=trade_account, auth=acc_manager.tq_auth)
            self.staker = RealStaker(
                self.tqApi, direction, trade_config.strategy_ids)

    def start_work(self):
        logger = self.logger
        logger.info('交易准备开始')
        self.staker.start_work()
