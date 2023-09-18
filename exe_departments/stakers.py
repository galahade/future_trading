import time
from abc import ABC, abstractmethod
from typing import List

from tqsdk import TqApi

import dao.config_service as c_service
import dao.trade_log.log_service as l_service
import utils.common_tools as c_tools
import utils.tqsdk_tools as tq_tools
from dao.odm.future_config import FutureConfigInfo
from dao.odm.trade_log import InvolvedSymbol, SymbolList, TradeRecord
from exe_departments.traders import MainStrategyTrader, Trader
from utils.common import LoggerGetter
from utils.config_utils import get_future_configs


class Staker(ABC):
    logger = LoggerGetter()
    """盯盘人，负责加载期货品种配置，并为每个品种生成一个交易人。当盯盘品种价格等参数发生改变时向交易人发送信号"""

    def __init__(self, api: TqApi, direction: int, strategy_ids: List[int]):
        self._api = api
        # 引入该变量是为了有一种可以和天勤服务器时间同步的方式判断是否处于交易时间的方法
        self._common_quote = api.get_quote("KQ.m@SHFE.au")
        self.direction = direction
        self.strategy_ids = strategy_ids
        self.future_configs: list[
            FutureConfigInfo
        ] = self._init_future_configs()
        self._init_status()
        self.trade_record = self._get_trade_record()

    def _init_status(self):
        """初始化盯盘人的状态，使得盯盘人可以进行下一日交易"""
        self.traders: List[Trader] = self._init_traders(
            self.direction, self.strategy_ids
        )

    def start_work(self):
        """执行盯盘操作

        每次程序运行该方法执行一次。除非被中断，否则不会停止。
        """
        logger = self.logger
        tr = self.trade_record
        tr.run_times += 1
        if tr.has_run_pre_opt and tr.has_run_post_opt and tr.has_trade:
            logger.info(
                f"本交易日 {tr.trade_date} 交易工作已完成."
                "系统将于晚19:30后开始运行下一交易日的工作".center(100, "*")
            )
            l_service.save_trade_record(tr)
        else:
            logger.debug("天勤服务器端已连接成功")
            logger.info(f"交易资金: {self._api.get_account().balance}")
            self.trade_record.current_balance = self._api.get_account().balance
            self._prepare_task()
            logger.info("交易准备工作完成 开始盯盘".center(100, "*"))
            self._handle_trade()

    def _handle_trade(self):
        """交易相关操作，包括盘前提示，交易，盘后操作

        当交易日结束后该函数将退出执行，然后重新生成trader并再次执行该函数。"""
        traders = list(filter(lambda t: t.is_active, self.traders))
        self._execute_before_trade()
        self._execute_trade(traders)
        self._execute_after_trade(traders)

    def _prepare_task(self):
        self.logger.info("当前配置的品种为:")
        tr = self.trade_record
        tr.config_mj_symbols = []
        tr.involved_main_symbols = []
        for trader in self.traders:
            mj_symbol = trader._config.f_info.symbol
            self.logger.info(f"{mj_symbol}")
            l_service.add_config_mj_symbol(tr, mj_symbol)
        self.logger.info("当前参与交易品种为:")
        for trader in filter(lambda t: t.is_active, self.traders):
            mj_symbol = trader._config.f_info.symbol
            involved_symbol = InvolvedSymbol()
            self.logger.info(f"{mj_symbol}")
            involved_symbol.mj_symbol = mj_symbol
            s_traders = trader.strategy_traders
            for strader in filter(lambda t: t.long_mjs is not None, s_traders):
                if isinstance(strader, MainStrategyTrader):
                    self.logger.info("主策略做多合约列表：")
                    c_symbol = strader.long_mjs.mjs_status.current_symbol
                    n_symbol = strader.long_mjs.mjs_status.next_symbol
                    l_symbol = SymbolList()
                    l_symbol.current_symbol = c_symbol
                    l_symbol.next_symbol = n_symbol
                    involved_symbol.long_symbols = l_symbol
                    self.logger.info(f"当前合约：{c_symbol}")
                    self.logger.info(f"下一合约：{n_symbol}")
            for strader in filter(
                lambda t: t.short_mjs is not None, s_traders
            ):
                if isinstance(strader, MainStrategyTrader):
                    self.logger.info("主策略做空合约列表：")
                    c_symbol = strader.short_mjs.mjs_status.current_symbol
                    n_symbol = strader.short_mjs.mjs_status.next_symbol
                    s_symbol = SymbolList()
                    s_symbol.current_symbol = c_symbol
                    s_symbol.next_symbol = n_symbol
                    involved_symbol.short_symbols = s_symbol
                    self.logger.info(f"当前合约：{c_symbol}")
                    self.logger.info(f"下一合约：{n_symbol}")
            l_service.add_involved_main_symbol(
                self.trade_record, involved_symbol
            )
        l_service.save_trade_record(self.trade_record)

    def _execute_before_trade(self):
        logger = self.logger
        tr = self.trade_record
        if not tr.has_run_pre_opt:
            for trader in self.traders:
                trader.execute_before_trade()
            logger.info("盘前提示结束 开始进入交易".center(100, "*"))
            tr.has_run_pre_opt = True
            l_service.save_trade_record(tr)
        else:
            logger.info("盘前提示信息已于之前产生 请访问数据库查看 开始进入交易".center(100, "*"))

    def _execute_trade(self, traders):
        logger = self.logger
        tr = self.trade_record
        if not tr.has_trade:
            # 在此调用该方法是为了确保当天是处于交易日。
            # 如果非交易日该方法应该不会返回。（有待验证）
            self._api.wait_update()
            while True:
                if c_tools.is_after_trade():
                    break
                elif tq_tools.is_trading_period(self._api, self._common_quote):
                    self._api.wait_update()
                    for trader in traders:
                        trader.execute_trade()
                else:
                    # 等待1分钟后尝试更新行情，并在等待超过15:10后返回
                    time.sleep(60)
                    self._api.wait_update(
                        deadline=tq_tools.get_break_time(self._common_quote)
                    )
            tr.has_trade = True
            l_service.save_trade_record(tr)
            logger.info("交易任务已结束，开始进行收盘操作".center(100, "*"))
        else:
            logger.info(
                "交易任务已完成，如有疑问，请修改数据库集合 trade_record.has_trade 后重新执行".center(
                    100, "*"
                )
            )

    def _execute_after_trade(self, traders):
        logger = self.logger
        tr = self.trade_record
        if not tr.has_run_post_opt:
            for trader in traders:
                trader.execute_after_trade()
        l_service.finish_trade_record(tr)
        logger.info("收盘工作完成".center(100, "*"))

    @abstractmethod
    def _init_future_configs(self) -> List[FutureConfigInfo]:
        """加载期货配置信息。

        首先在系统文件系统加载初始期货配置信息，实盘和回测的配置文件路径不同，
        当数据库中有期货配置信息时，将数据库中的期货配置信息覆盖掉系统文件系统中的配置信息。
        否则，使用系统文件系统中的配置信息为数据库初始化期货配置信息。
        """

    @abstractmethod
    def _init_traders(self, d: int, strategy_ids: List[int]) -> List[Trader]:
        """根据期货配置信息为每个品种生成一个交易员

        Args:
            d: 交易方向, 交易员使用它来决定策略交易员的方向类型
            strategy_ids: 策略id列表, 交易员使用它来决定策略交易员的策略类型
        """

    @abstractmethod
    def _get_trade_record(self) -> TradeRecord:
        """根据不同类型的顶盘人，使用不同逻辑获取交易记录"""


class RealStaker(Staker):
    """实盘交易盯盘人"""

    def _init_future_configs(self) -> List[FutureConfigInfo]:
        return c_service.get_future_configs(get_future_configs())

    def _init_traders(self, d, strategy_ids) -> List[Trader]:
        """加载交易员"""
        traders = []
        for f_config in self.future_configs:
            traders.append(Trader(self._api, f_config, strategy_ids, d, False))
        return traders

    def _get_trade_record(self) -> TradeRecord:
        return l_service.get_trade_record(
            c_tools.get_trade_date(c_tools.get_china_tz_now())
        )


class BTStaker(Staker):
    """回测交易盯盘人"""

    def _get_trade_record(self) -> TradeRecord:
        return None

    def _init_future_configs(self) -> List[FutureConfigInfo]:
        return c_service.get_future_configs(
            get_future_configs(is_backtest=True)
        )

    def _init_traders(self, d, strategy_ids) -> List[Trader]:
        """加载交易员"""
        traders = []
        for config in self.future_configs:
            traders.append(Trader(self._api, config, strategy_ids, d, True))
        return traders

    def _prepare_task(self):
        """交易前的准备工作, 实盘交易打印出参与交易品种的合约信息，回测交易打印出回测的起止时间"""
        super()._prepare_task()

    def _handle_trade(self):
        """交易相关操作，包括盘前提示，交易，盘后操作

        当交易日结束后该函数将退出执行，然后重新生成trader并再次执行该函数。"""
        logger = self.logger
        for trader in self.traders:
            trader.execute_before_trade()
        logger.info("盘前提示结束，开始进入交易".center(100, "*"))
        while True:
            traders = filter(
                lambda t: t.is_active and not t.is_finished, self.traders
            )
            # 当所有交易员当日交易结束后，退出循环
            traders = list(traders)
            if len(traders) == 0:
                logger.debug("所有交易员当日交易结束，退出交易".center(100, "*"))
                break
            self._api.wait_update()
            for trader in traders:
                trader.execute_trade()

    def start_work(self):
        """执行盯盘操作

        每次程序运行该方法执行一次。除非被中断，否则不会停止。
        """
        logger = self.logger
        logger.info(f"交易初始资金为{self._api.get_account().balance}")
        # self._api.wait_update()
        logger.info("天勤服务器端已连接成功")
        self._prepare_task()
        logger.info("交易准备工作完成，开始盯盘".center(100, "*"))
        while True:
            self._handle_trade()
            self._init_status()
