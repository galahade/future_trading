from mongoengine import (
    Document,
    EmbeddedDocument,
    StringField,
    FloatField,
    BooleanField,
    EmbeddedDocumentField,
    ListField,
    IntField,
)


class LongConfig(EmbeddedDocument):
    # 止盈止损基础比例
    base_scale: float = FloatField()
    # 止损倍数
    stop_loss_scale: float = FloatField()
    # 开始止盈倍数
    profit_start_scale_1: float = FloatField()
    # 开始止盈2倍数
    profit_start_scale_2: float = FloatField()
    # 提高止损需达到的倍数
    promote_scale_1: float = FloatField()
    # 提高止损需达到的倍数2
    promote_scale_2: float = FloatField()
    # 将止损提高的倍数
    promote_target_1: float = FloatField()
    # 将止损提高的倍数2
    promote_target_2: float = FloatField()


class ShortConfig(EmbeddedDocument):
    # 止盈止损基础比例
    base_scale: float = FloatField(required=True)
    # 止损倍数
    stop_loss_scale: float = FloatField()
    # 开始止盈倍数
    profit_start_scale: float = FloatField()
    # 提高止损需达到的倍数
    promote_scale: float = FloatField()
    # 将止损提高的倍数
    promote_target: float = FloatField()


class FutureConfigInfo(Document):
    # 期货合约加交易所的表示方法
    symbol: str = StringField(unique=True, required=True)
    # 是否对该品种进行交易
    is_active: bool = BooleanField(required=True)
    # 合约中文名称
    name: str = StringField(required=True)
    multiple: int = IntField(required=True)
    # 开仓金额占粽资金的比例
    open_pos_scale: float = FloatField()
    # 换月时间距离交割日的天数
    switch_days: list[int] = ListField()
    # 该品种的主力合约列表
    main_symbols: list[str] = ListField()
    long_config: LongConfig = EmbeddedDocumentField(LongConfig)
    short_config: ShortConfig = EmbeddedDocumentField(ShortConfig)
