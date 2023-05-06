from mongoengine import (
    Document, EmbeddedDocument, StringField, FloatField,
    BooleanField,  EmbeddedDocumentField, ListField)


class LongConfig(EmbeddedDocument):
    # 止盈止损基础比例
    base_scale = FloatField()
    # 止损倍数
    stop_loss_scale = FloatField()
    # 开始止盈倍数
    profit_start_scale_1 = FloatField()
    # 开始止盈2倍数
    profit_start_scale_2 = FloatField()
    # 提高止损需达到的倍数
    promote_scale_1 = FloatField()
    # 提高止损需达到的倍数2
    promote_scale_2 = FloatField()
    # 将止损提高的倍数
    promote_target_1 = FloatField()
    # 将止损提高的倍数2
    promote_target_2 = FloatField()


class ShortConfig(EmbeddedDocument):
    # 止盈止损基础比例
    base_scale = FloatField(required=True)
    # 止损倍数
    stop_loss_scale = FloatField()
    # 开始止盈倍数
    profit_start_scale = FloatField()
    # 提高止损需达到的倍数
    promote_scale = FloatField()
    # 将止损提高的倍数
    promote_target = FloatField()


class FutureConfigInfo(Document):
    # 期货合约加交易所的表示方法
    symbol = StringField(required=True)
    # 是否对该品种进行交易
    is_active = BooleanField(required=True)
    # 合约中文名称
    name = StringField(required=True)
    # 开仓金额占粽资金的比例
    open_pos_scale = FloatField()
    # 换月时间距离交割日的天数
    switch_days = ListField()
    # 该品种的主力合约列表
    main_symbols = ListField()
    long_config = EmbeddedDocumentField(LongConfig)
    short_config = EmbeddedDocumentField(ShortConfig)
