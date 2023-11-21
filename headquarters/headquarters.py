from typing import Optional

from mongoengine import connect
from tqsdk import TqApi, TqAuth, TqBacktest, TqKq, TqSim

import dao.config_service as c_service
import utils.config_utils as c_utils
from dao.odm.trade_config import TradeConfigInfo
from exe_departments.stakers import BTStaker, RealStaker

# from utils import global_var as gvar
from utils.common_tools import LoggerGetter, tz_utc_8
from utils.config_utils import SystemConfig


class Commander:
    """期货交易总指挥，根据交易系统配置生成支持交易的各种角色，并协调完成交易工作

    交易角色包括：
        DBA：管理数据库连接。将对接好的数据库交给其他角色使用。
        AccountManager：管理交易账户。根据交易系统配置生成交易账户.
        TradeManager：交易主管。负责利用系统提供的资源开展交易工作。
    """

    def __init__(self):
        _config = c_utils.get_system_config()
        self._dba = DBA(_config)
        self._dba.create_db()
        self._account_manager = AccountManager(
            c_service.get_system_config(_config)
        )
        self.trade_manager = TradeManager(self._account_manager)

    def start_work(self):
        """交易的开端"""
        self.trade_manager.start_work()


class DBA:
    """使用系统配置文件中的MongoDB配置信息，连接MongoDB数据库"""

    def __init__(self, config: SystemConfig):
        mongo_config = config.mongo_config
        self._trade_config = config.trade_config
        host = mongo_config.host
        port = mongo_config.port
        if hasattr(mongo_config, "user"):
            user = mongo_config.user
            password = mongo_config.password
            self._url = f"mongodb://{user}:{password}@{host}:{port}/"
        else:
            self._url = f"mongodb://{host}:{port}/"

    def create_db(self, db_name: Optional[str] = None):
        # if db_name is None:
        #     if self._trade_config.is_backtest:
        #         db_name = str(uuid.uuid4())
        #     else:
        #         db_name = "future_trade"
        if db_name is None:
            db_name = "future_trade"
        db_url = f"{self._url}{db_name}?authSource=admin"
        connect(host=db_url, tz_aware=True, tzinfo=tz_utc_8)


class AccountManager:
    def __init__(self, trade_config: TradeConfigInfo):
        self.trade_config = trade_config
        _tq_acc = trade_config.tq_account
        self._acc_type = trade_config.account_type
        #  0:模拟账户 1:天勤实盘
        if self._acc_type == 1:
            # 尚未启用该类型账户
            self.trade_account = None
        else:
            print(trade_config.account_balance)
            # TqSim 账户的交易信息保存在内存中，当平仓时会因为系统重启而发生平仓手数不足的错误
            # TqKq 是将交易信息保存在服务端，需要使用不同number来根据不同环境分配资金。
            # self.trade_account = TqSim(init_balance=trade_config.account_balance)
            if self.trade_config.is_backtest:
                self.trade_account = TqSim(init_balance=10000000)
            else:
                # 以下功能需要购买专业版
                # self.trade_account = TqKq(number=gvar.TQKQ_NUMBER)
                self.trade_account = TqKq()
        self.tq_auth = TqAuth(_tq_acc.user_name, _tq_acc.password)

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
            self.logger.info("使用回测模式")
            self.tqApi = TqApi(
                account=trade_account,
                auth=acc_manager.tq_auth,
                backtest=TqBacktest(
                    start_dt=trade_config.backtest_days.start_date,
                    end_dt=trade_config.backtest_days.end_date,
                ),
            )
            self.staker = BTStaker(
                self.tqApi, direction, trade_config.strategy_ids
            )
        else:
            self.logger.info("使用实盘模式")
            if acc_manager.is_real_account():
                self.logger.info("使用实盘账户进行交易")
            else:
                self.logger.info("使用模拟账户进行交易")
            self.tqApi = TqApi(account=trade_account, auth=acc_manager.tq_auth)
            self.staker = RealStaker(
                self.tqApi, direction, trade_config.strategy_ids
            )

    def start_work(self):
        logger = self.logger
        logger.info("交易准备开始")
        self.staker.start_work()
        self.tqApi.close()
