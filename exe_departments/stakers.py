import time
from abc import ABC, abstractmethod
from datetime import datetime

from tqsdk import BacktestFinished, TqApi, tafunc

import dao.config_service as c_service
import dao.trade_log.log_service as l_service
import utils.common_tools as c_tools
import utils.email_tools as email_tools
import utils.tqsdk_tools as tq_tools
from dao.odm.future_config import FutureConfigInfo
from dao.odm.trade_log import InvolvedSymbol, SymbolList, TradeRecord
from exe_departments.traders import MainStrategyTrader, TestTrader, Trader
from utils.config_utils import get_future_configs


class Staker(ABC):
    logger = c_tools.LoggerGetter()
    """盯盘人，负责加载期货品种配置，并为每个品种生成一个交易人。当盯盘品种价格等参数发生改变时向交易人发送信号"""

    def __init__(self, api: TqApi, direction: int, strategy_ids: list[int]):
        self._api = api
        # 引入该变量是为了有一种可以和天勤服务器时间同步的方式判断是否处于交易时间的方法
        self._common_quote = api.get_quote("KQ.m@SHFE.au")
        self.direction = direction
        self.strategy_ids = strategy_ids
        self.future_configs: list[
            FutureConfigInfo
        ] = self._init_future_configs()
        self._init_status()

    def _init_status(self):
        """初始化盯盘人的状态，使得盯盘人可以进行下一日交易"""
        self.traders: list[Trader] = self._init_traders(
            self.direction, self.strategy_ids
        )

    def _handle_trade(self):
        """交易相关操作，包括盘前提示，交易，盘后操作
        当交易日结束后该函数将退出执行，然后重新生成trader并再次执行该函数。"""
        traders = list(filter(lambda t: t.is_active, self.traders))
        self._execute_before_trade()
        self._execute_trade(traders)

    @abstractmethod
    def start_work(self):
        """执行盯盘操作
        每次程序运行该方法执行一次。除非被中断，否则不会停止。
        """

    @abstractmethod
    def _prepare_task(self):
        """为交易提供相关数据"""

    @abstractmethod
    def _execute_before_trade(self) -> bool:
        """执行换月，盘前提示等相关操作"""

    @abstractmethod
    def _execute_trade(self, traders: list[Trader]):
        """执行交易操作"""

    @abstractmethod
    def _execute_after_trade(self, traders: list[Trader]):
        """执行收盘后的相关操作"""

    @abstractmethod
    def _init_future_configs(self) -> list[FutureConfigInfo]:
        """加载期货配置信息。

        首先在系统文件系统加载初始期货配置信息，实盘和回测的配置文件路径不同，
        当数据库中有期货配置信息时，将数据库中的期货配置信息覆盖掉系统文件系统中的配置信息。
        否则，使用系统文件系统中的配置信息为数据库初始化期货配置信息。
        """

    @abstractmethod
    def _init_traders(self, d: int, strategy_ids: list[int]) -> list[Trader]:
        """根据期货配置信息为每个品种生成一个交易员

        Args:
            d: 交易方向, 交易员使用它来决定策略交易员的方向类型
            strategy_ids: 策略id列表, 交易员使用它来决定策略交易员的策略类型
        """


class RealStaker(Staker):
    """实盘交易盯盘人"""

    def __init__(self, api: TqApi, direction: int, strategy_ids: list[int]):
        super().__init__(api, direction, strategy_ids)
        self.trade_record = self._get_trade_record()

    def _init_future_configs(self) -> list[FutureConfigInfo]:
        return c_service.get_future_configs(get_future_configs())

    def _init_traders(self, d, strategy_ids) -> list[Trader]:
        """加载交易员"""
        traders = []
        for f_config in self.future_configs:
            traders.append(Trader(self._api, f_config, strategy_ids, d, False))
        return traders

    def _get_trade_record(self) -> TradeRecord:
        return l_service.get_trade_record(
            c_tools.get_trade_date(c_tools.get_china_tz_now())
        )

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
        if tr.has_run_pre_opt:
            logger.info("盘前提示信息已于之前产生 请访问数据库查看 开始进入交易".center(100, "*"))
        else:
            if c_tools.after_trade_time():
                logger.info("盘前提示运行时间段为每日19:15之后。请耐心等待".center(100, "*"))
            else:
                self._prepare_task()
                for trader in self.traders:
                    trader.execute_before_trade()
                logger.info("盘前提示结束 开始进入交易".center(100, "*"))
                tr.has_run_pre_opt = True
                l_service.save_trade_record(tr)
                email_tools.send_before_trading_message()

    def _execute_trade(self, traders: list[Trader]) -> bool:
        logger = self.logger
        tr = self.trade_record
        if tr.has_trade and c_tools.before_trade_time():
            logger.info(
                "交易任务已完成，如有疑问，请修改数据库集合 trade_record.has_trade 后重新执行".center(
                    100, "*"
                )
            )
        else:
            if c_tools.none_trade_time():
                logger.info("当前为非交易时段，系统将会稍后重试".center(100, "*"))
            else:
                c_tools.sendSystemStartupMsg(
                    datetime.now(), self.direction, self.strategy_ids
                )
                self._api.wait_update()
                while True:
                    if c_tools.none_trade_time():
                        break
                    elif tq_tools.is_trading_period(
                        self._api, self._common_quote
                    ):
                        self._api.wait_update()
                        for trader in traders:
                            trader.execute_trade()
                    else:
                        # 等待1分钟后尝试更新行情，并在等待超过15:10后返回
                        time.sleep(60)
                        self._api.wait_update(
                            deadline=tq_tools.get_break_time(
                                self._common_quote
                            )
                        )
                if c_tools.before_trade_time():
                    tr.has_trade = True
                    l_service.save_trade_record(tr)
                    logger.info("交易任务已结束，开始进行收盘操作".center(100, "*"))
                    self._execute_after_trade(traders)

    def _execute_after_trade(self, traders: list[Trader]):
        logger = self.logger
        tr = self.trade_record
        if not tr.has_run_post_opt:
            for trader in traders:
                trader.execute_after_trade()
        l_service.finish_trade_record(tr)
        logger.info("收盘工作完成".center(100, "*"))

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
            # self._prepare_task()
            logger.info("交易准备工作完成 开始盯盘".center(100, "*"))
            self._handle_trade()


class BTStaker(Staker):
    """回测交易盯盘人"""

    def __init__(self, api: TqApi, direction: int, strategy_ids: list[int]):
        super().__init__(api, direction, strategy_ids)

    def _init_future_configs(self) -> list[FutureConfigInfo]:
        return c_service.get_future_configs(
            get_future_configs(), is_backtest=True
        )

    def _init_traders(self, d, strategy_ids) -> list[Trader]:
        """加载交易员"""
        self.quote_time = tafunc.time_to_datetime(
            self._common_quote.datetime
        ).strftime("%Y-%m-%d %H:%M:%S")
        traders = []
        for config in self.future_configs:
            traders.append(
                TestTrader(self._api, config, strategy_ids, d, True)
            )
        self.logger.debug("reinit traders fininshed")
        return traders

    def _prepare_task(self):
        """交易前的准备工作, 回测交易打印出回测的起止时间"""
        start_date = tafunc.time_to_datetime(
            self._api._backtest._start_dt
        ).strftime("%Y-%m-%d %H:%M:%S")
        end_date = tafunc.time_to_datetime(
            self._api._backtest._end_dt
        ).strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"回测开始时间:{start_date}，回测结束时间:{end_date}")
        self.logger.info("当前配置的品种为:")
        for trader in self.traders:
            mj_symbol = trader._config.f_info.symbol
            self.logger.info(f"{mj_symbol}")
        self.logger.info("当前参与交易品种为:")
        for trader in filter(lambda t: t.is_active, self.traders):
            mj_symbol = trader._config.f_info.symbol
            self.logger.info(f"{mj_symbol}")

    def _handle_trade(self):
        """回测交易相关操作，在其中循环每天交易操作
        回测时该函数在没有运行到截止日期前不会退出
        """
        while True:
            # 每完成一个循环，需要重新生成 traders 来初始化日线条件
            self._api.wait_update()
            self.traders = self._init_traders(
                self.direction, self.strategy_ids
            )
            traders = list(filter(lambda t: t.is_active, self.traders))
            self._execute_before_trade()
            self._execute_trade(traders)
            self._execute_after_trade()

    def start_work(self):
        """执行盯盘操作
        每次程序运行该方法执行一次。除非被中断，否则不会停止。
        """
        logger = self.logger
        logger.info(f"回测初始资金为{self._api.get_account().balance}")
        logger.info("天勤服务器端已连接成功")
        self._prepare_task()
        logger.info("准备工作已完成，开始回测".center(100, "*"))
        try:
            self._handle_trade()
        except BacktestFinished:
            logger.info("回测完成")
            logger.info(self._api._account.tqsdk_stat)
            # api.close()
            # 打印回测的详细信息
            # logger.info(self._api._account.trade_log)
            # 账户交易信息统计结果
            # print("tqsdk stat:", acc.tqsdk_stat)
            while True:
                self._api.wait_update()

    def _execute_before_trade(self):
        """执行换月操作"""
        logger = self.logger
        for trader in self.traders:
            trader.execute_before_trade()
        logger.info((f"{self.quote_time}-盘前提示结束 开始进入交易").center(100, "*"))

    def _execute_trade(self, traders: list[Trader]):
        logger = self.logger
        while tq_tools.is_trading_period(self._api, self._common_quote):
            self._api.wait_update()
            for trader in traders:
                trader.execute_trade()
        logger.info((f"{self.quote_time}-交易结束 开始进入盘后操作").center(100, "*"))

    def _execute_after_trade(self):
        logger = self.logger
        logger.debug("回测无须收盘操作-跳过")
