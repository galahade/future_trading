from datetime import datetime
from mongoengine import (
    Document, EmbeddedDocument, StringField, IntField, FloatField,
    DateTimeField, BooleanField,  EmbeddedDocumentField, ListField,
    ReferenceField)


class IndicatorValues(EmbeddedDocument):
    '''指标值'''
    meta = {'abstract': True}

    ema60 = FloatField()
    macd = FloatField()
    close = FloatField()
    kline_time = DateTimeField()

    def clear(self):
        self.ema60 = 0.0
        self.macd = 0.0
        self.close = 0.0
        self.kline_time = None


class BottomIndicatorValues(IndicatorValues):
    '''指标值'''
    ema5 = FloatField()
    ema20 = FloatField()

    def clear(self):
        super().clear()
        self.ema5 = 0.0
        self.ema20 = 0.0


class MainIndicatorValues(IndicatorValues):
    '''主策略的指标值'''
    ema9 = FloatField()
    ema22 = FloatField()
    open = FloatField()
    condition_id = IntField()

    def clear(self):
        self.ema9 = 0.0
        self.ema22 = 0.0
        self.open = 0.0


class OpenCondition(EmbeddedDocument):
    '''开仓满足的条件，包括：日线条件，3小时条件， 30分钟条件 的类型'''
    # 开仓条件
    daily_condition = EmbeddedDocumentField(IndicatorValues)
    hourly_condition = EmbeddedDocumentField(IndicatorValues)
    minute_30_condition = EmbeddedDocumentField(IndicatorValues)

    def clear(self):
        self.daily_condition = None
        self.hourly_condition = None
        self.minute_30_condition = None


class BottomOpenCondition(OpenCondition):
    pass


class MainOpenCondition(OpenCondition):
    '''主策略开仓满足的条件，包括：日线条件，3小时条件， 30分钟条件 5分钟线 等类型'''
    # 开仓条件
    minute_5_condition = EmbeddedDocumentField(MainIndicatorValues)

    def clear(self):
        super().clear()
        self.minute_5_condition = None


class SoldCondition(EmbeddedDocument):
    '''存储平仓用到的条件'''
    # 止盈阶段
    take_profit_stage = IntField(default=0)
    # 该交易适用的止盈条件
    take_profit_cond = IntField(default=0)
    # 止损价格
    stop_loss_price = FloatField(default=0.0)
    # 是否已经提高止损价
    has_increase_slp = BooleanField(default=False)
    # 止损原因
    sl_reason = StringField(default='止损')
    # 止盈监控开始价格
    tp_started_point = FloatField(default=0.0)
    # 是否进入止盈阶段
    has_enter_tp = BooleanField(default=False)
    # 是否停止跟踪止盈
    has_stop_tp = BooleanField(default=False)

    def clear(self):
        self.take_profit_stage = 0
        self.take_profit_cond = 0
        self.stop_loss_price = 0.0
        self.has_increase_slp = False
        self.sl_reason = '止损'
        self.tp_started_point = 0.0
        self.has_enter_tp = False
        self.has_stop_tp = False


class BottomSoldCondition(SoldCondition):
    '''摸底策略的平仓条件'''


class MainSoldCondition(SoldCondition):
    '''存储平仓用到的条件'''


class TradePosBase(Document):
    '''开平仓信息的基类'''
    meta = {'abstract': True}
    # 期货合约
    symbol = StringField(required=True)
    # 交易方向：0: 做空，1: 做多
    direction = IntField(required=True, min_value=0, max_value=1)
    # 开仓价格
    trade_price = FloatField()
    # 开仓数量
    volume = IntField()
    # 交易时间
    trade_time = DateTimeField()
    # 系统订单id
    order_id = StringField()
    last_modified = DateTimeField()


class CloseVolume(TradePosBase):
    meta = {'abstract': True}
    '''存储期货合约的平仓信息'''
    # 平仓类型 0: 止损, 1: 止盈, 2: 换月, 3: 人工平仓
    close_type = IntField()
    close_message = StringField()


class MainCloseVolume(CloseVolume):
    '''存储期货合约主策略平仓信息'''


class MainOpenVolume(TradePosBase):
    '''存储某个期货合约的开仓信息，包括：
    期货合约，交易方向，开仓价格，开仓时间，开仓订单id，开仓条件，是否平仓，平仓信息id，最后更新时间
    '''
    # 开仓条件
    open_condition = EmbeddedDocumentField(MainOpenCondition)
    # 是否平仓
    is_close = BooleanField(required=True, default=False)
    # 平仓信息
    close_pos_infos = ListField(ReferenceField(MainCloseVolume))


class BottomOpenVolumeTip(Document):
    '''摸底策略开仓盘前提示信息'''
    custom_symbol = StringField(required=True)
    # 期货合约
    symbol = StringField(required=True)
    # 最近一根日k线时间
    dkline_time = DateTimeField()
    # 交易方向：0: 做空，1: 做多
    direction = IntField(required=True, min_value=0, max_value=1)
    # 上一交易日收盘价格
    last_price = FloatField()
    # 开仓数量
    volume = IntField()
    last_modified = DateTimeField()
    # 开仓条件
    open_condition = EmbeddedDocumentField(BottomOpenCondition)


class BottomCloseVolume(CloseVolume):
    '''存储期货合约主策略平仓信息'''


class BottomOpenVolume(TradePosBase):
    # 盘前提示记录
    tip = ReferenceField(BottomOpenVolumeTip)
    # 是否平仓
    is_close = BooleanField(required=True, default=False)
    # 平仓信息
    close_pos_infos = ListField(ReferenceField(BottomCloseVolume))


class TradeStatus(Document):
    '''具体合约需要保存的交易状态基类'''
    meta = {
        'abstract': True,
        'indexes': [
            {
                'fields': ['symbol', 'direction'],
                'unique': True
            }
        ]}
    # 主连合约+交易策略+交易方向
    custom_symbol = StringField(required=True)
    symbol = StringField(required=True)
    # 交易方向：0: 做空，1: 做多
    direction = IntField(required=True, min_value=0, max_value=1)
    # 交易状态：0: 未开始，1: 交易中，2: 已平仓
    trade_status = IntField(default=0)
    # 持仓数量, 已开仓数量 - 已平仓数量
    carrying_volume = IntField(default=0)
    # 开始交易时间
    start_time = DateTimeField()
    # 结束交易时间
    end_time = DateTimeField()
    last_modified = DateTimeField()
    open_condition: OpenCondition = None
    sold_condition: SoldCondition = None
    open_pos_info = None

    def closeout(self, end_time: datetime):
        '''平仓'''
        self.trade_status = 2
        self.carrying_volume = 0
        self.end_time = end_time
        self.open_pos_info = None
        self.last_modified = end_time
        self._clear_conditions()

    def _clear_conditions(self):
        '''清除开仓和平仓条件'''
        self.open_condition.clear()
        self.sold_condition.clear()

    def switch_symbol(self, symbol: str, dt: datetime):
        '''切换合约'''
        self.symbol = symbol
        self.trade_status = 0
        self.carrying_volume = 0
        self.start_time = None
        self.end_time = None
        self.open_pos_info = None
        self.last_modified = dt
        self._clear_conditions()


class MainTradeStatus(TradeStatus):
    # 开仓信息
    open_condition = EmbeddedDocumentField(MainOpenCondition)
    sold_condition = EmbeddedDocumentField(MainSoldCondition)
    open_pos_info = ReferenceField(MainOpenVolume)


class BottomTradeStatus(TradeStatus):
    # 开仓信息
    open_condition = EmbeddedDocumentField(BottomOpenCondition)
    sold_condition = EmbeddedDocumentField(BottomSoldCondition)
    open_pos_info = ReferenceField(BottomOpenVolume)


class MainJointSymbolStatus(Document):
    '''主连合约状态的基类
 
    主连合约的多空方向都有一个主连合约状态，故一个双向交易的主连合约，每种策略都有两个主连合约状态
    '''
    meta = {'abstract': True}
    # 主连合约+交易策略+交易方向
    custom_symbol = StringField(required=True, unique=True)
    # 主连合约
    main_joint_symbol = StringField(required=True)
    # 当前跟踪合约，有可能是当前主力合约，也有可能是上一个主力合约
    current_symbol = StringField(required=True)
    # 当前合约之后的主力合约，有可能是下一个主力合约，也有可能是当前主力合约
    next_symbol = StringField(required=True)
    # 交易方向: 0: 做空，1: 做多
    direction = IntField(required=True)
    last_modified = DateTimeField()

    def switch_symbol(self, new_symbol: str, switch_time: datetime):
        '''切换合约时需要更新的信息'''
        self.current_symbol = self.next_symbol
        self.next_symbol = new_symbol
        self.last_modified = switch_time
