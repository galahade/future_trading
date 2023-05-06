# from dao.trade_service import(
#     get_mjss, get_symbol_status, get_opi, save_opi, save_cpi, get_opi
# )
# from headquarters.headquarters import DBA
# from utils.config_utils import get_system_config
# from utils.common_tools import get_china_tz_now


# class TestClass:
    # def setup_db(self):
    #     sys_config = get_system_config()
    #     DBA(sys_config)

    # def test_get_mjss(self):
    #     '''测试 create_mjss 方法是否能够正确创建主连合约交易状态信息'''
    #     self.setup_db()
    #     mjss = get_mjss('KQ.m@DCE.a', 'a2305', 'a2309', 2)

    #     assert mjss.main_joint_symbol == 'KQ.m@DCE.a'
    #     assert mjss.current_symbol == 'a2305'
    #     assert mjss.next_symbol == 'a2309'
    #     assert mjss.direction == 2
    #     assert len(mjss.current_symbol_status) == 2
    #     assert len(mjss.next_symbol_status) == 2

    # # def test_get_symbol_status(self):
    # #     '''测试 get_symbol_status 方法是否能够正确读取主连合约交易状态信息'''
    # #     self.setup_db()
    # #     ss = get_symbol_status('a2309', 1)
    # #     assert ss.symbol == 'a2309'
    # #     assert ss.custom_symbol == 'DCE_a_long'
    # #     assert ss.direction == 1
    # #     assert ss.trade_status == 0
    # #     assert ss.carrying_volume == 0

    # # def test_create_openposinfo(self):
    # #     '''测试 saveOpenPosInfo 方法是否能够正确创建开仓信息'''
    # #     self.setup_db()
    # #     ss = get_symbol_status('a2309', 1)
    # #     opd = dict()
    # #     opd['trade_price'] = 100
    # #     opd['volume'] = 2
    # #     opd['trade_time'] = get_china_tz_now()
    # #     opd['order_id'] = '123456'
    # #     opd['open_conditions'] = dict()
    # #     opd['open_conditions']['daily_condition'] = 1
    # #     opd['open_conditions']['hourly_condition'] = 2
    # #     opd['open_conditions']['minute_30_condition'] = 3
    # #     opd['sold_conditions'] = dict()
    # #     opd['sold_conditions']['take_profit_stage'] = 1
    # #     opd['sold_conditions']['tp_cond'] = 2
    # #     opd['sold_conditions']['stop_loss_price'] = 99
    # #     opd['sold_conditions']['has_increase_slp'] = False
    # #     opd['sold_conditions']['sl_reason'] = '测试'
    # #     opd['sold_conditions']['tp_started_point'] = 101
    # #     opd['sold_conditions']['has_enter_tp'] = False
    # #     opd['sold_conditions']['has_stop_tp'] = False
    # #     opi = save_opi(ss, opd)
    # #     assert opi.symbol == 'a2309'
    # #     assert opi.direction == 1
    # #     assert opi.trade_price == 100
    # #     assert opi.volume == 2
    # #     assert opi.order_id == '123456'
    # #     assert opi.open_condition.daily_condition == 1
    # #     assert opi.open_condition.hourly_condition == 2
    # #     assert opi.open_condition.minute_30_condition == 3
    # #     assert opi.sold_condition.take_profit_stage == 1
    # #     assert opi.sold_condition.tp_cond == 2
    # #     assert opi.sold_condition.stop_loss_price == 99
    # #     assert opi.sold_condition.has_increase_slp is False
    # #     assert opi.sold_condition.sl_reason == '测试'
    # #     assert opi.sold_condition.tp_started_point == 101
    # #     assert opi.sold_condition.has_enter_tp is False
    # #     assert opi.sold_condition.has_stop_tp is False

    # def test_get_open_pos_info(self):
    #     self.setup_db()
    #     ss = get_symbol_status('a2309', 1)
    #     opi = ss.open_pos_info
    #     assert opi.symbol == 'a2309'
    #     assert opi.direction == 1
    #     assert opi.trade_price == 100
    #     assert opi.volume == 2
    #     assert opi.order_id == '123456'
    #     assert opi.open_condition.daily_condition == 1
    #     assert opi.open_condition.hourly_condition == 2
    #     assert opi.open_condition.minute_30_condition == 3
    #     assert opi.sold_condition.take_profit_stage == 1
    #     assert opi.sold_condition.tp_cond == 2
    #     assert opi.sold_condition.stop_loss_price == 99
    #     assert opi.sold_condition.has_increase_slp is False
    #     assert opi.sold_condition.sl_reason == '测试'
    #     assert opi.sold_condition.tp_started_point == 101
    #     assert opi.sold_condition.has_enter_tp is False
    #     assert opi.sold_condition.has_stop_tp is False
    #     # assert ss.carrying_volume == 2
    #     # assert ss.trade_status == 1
    #     # assert ss.start_time == opi.trade_time

    # # def test_create_closeposinfo(self):
    # #     '''测试 saveClosePosInfo 方法是否能够正确创建平仓信息'''
    # #     self.setup_db()
    # #     ss = get_symbol_status('a2309', 1)
    # #     cpd = dict()
    # #     cpd['trade_price'] = 120
    # #     cpd['volume'] = 1
    # #     cpd['trade_time'] = get_china_tz_now()
    # #     cpd['order_id'] = '123457'
    # #     cpi = save_cpi(ss, cpd)
    # #     assert cpi.symbol == 'a2309'
    # #     assert cpi.direction == 1
    # #     assert cpi.trade_price == 120
    # #     assert cpi.volume == 1
    # #     assert cpi.order_id == '123457'

    # #     cpd['trade_price'] = 130
    # #     cpd['volume'] = 1
    # #     cpd['trade_time'] = get_china_tz_now()
    # #     cpd['order_id'] = '123458'
    # #     cpi = saveClosePosInfo(ss, cpd)
    # #     assert ss.carrying_volume == 0
    # #     assert ss.trade_status == 0
    # #     assert ss.end_time == cpi.trade_time
    # #     assert len(ss.open_pos_info.close_pos_info) == 2

    # def test_get_open_pos_info_alone(self):
    #     self.setup_db()
    #     opi = get_opi('a2309', 1)
    #     assert opi.symbol == 'a2309'
    #     assert opi.direction == 1
    #     assert opi.trade_price == 100
    #     assert opi.volume == 2
    #     assert opi.order_id == '123456'
    #     assert opi.open_condition.daily_condition == 1
    #     assert opi.open_condition.hourly_condition == 2
    #     assert opi.open_condition.minute_30_condition == 3
    #     assert opi.sold_condition.take_profit_stage == 1
    #     assert opi.sold_condition.tp_cond == 2
    #     assert opi.sold_condition.stop_loss_price == 99
    #     assert opi.sold_condition.has_increase_slp is False
    #     assert opi.sold_condition.sl_reason == '测试'
    #     assert opi.sold_condition.tp_started_point == 101
    #     assert opi.sold_condition.has_enter_tp is False
    #     assert opi.sold_condition.has_stop_tp is False