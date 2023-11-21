from datetime import datetime
from typing import List

from mongoengine import (
    BooleanField,
    DateTimeField,
    Document,
    EmbeddedDocument,
    EmbeddedDocumentField,
    FloatField,
    IntField,
    ListField,
    StringField,
)


class Account(EmbeddedDocument):
    meta = {"allow_inheritance": True}
    user_name = StringField(required=True)
    password = StringField(required=True)


class RohonAccount(Account):
    app_id = StringField()
    auth_code = StringField()
    broker_id = StringField()
    url = StringField()


class BacktestDays(EmbeddedDocument):
    start_date: datetime = DateTimeField()
    end_date: datetime = DateTimeField()


class TradeConfigInfo(Document):
    direction: int = IntField(required=True, default=2)
    is_backtest: bool = BooleanField(required=True, default=False)
    account_type: int = IntField(required=True, default=0)
    account_balance: float = FloatField(default=10000000.00)
    strategy_ids: List[int] = ListField(IntField(), default=[1, 2])
    backtest_days: BacktestDays = EmbeddedDocumentField(BacktestDays)
    tq_account: Account = EmbeddedDocumentField(Account)
    rohon_account: RohonAccount = EmbeddedDocumentField(RohonAccount)
    date_time: datetime = DateTimeField()
