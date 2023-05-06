from mongoengine import (
    EmbeddedDocument, StringField, IntField, BooleanField,
    ListField, DateTimeField, Document, EmbeddedDocumentField)


class Account(EmbeddedDocument):
    meta = {'allow_inheritance': True}
    user_name = StringField(required=True)
    password = StringField(required=True)


class RohonAccount(Account):
    app_id = StringField()
    auth_code = StringField()
    broker_id = StringField()
    url = StringField()


class BacktestDays(EmbeddedDocument):
    start_date = DateTimeField()
    end_date = DateTimeField()


class TradeConfigInfo(Document):
    direction = IntField(required=True, default=2)
    is_backtest = BooleanField(required=True, default=False)
    account_type = IntField(required=True, default=0)
    strategies = ListField(IntField(), default=[1, 2])
    backtest_days = EmbeddedDocumentField(BacktestDays)
    tq_account = EmbeddedDocumentField(Account)
    rohon_account = EmbeddedDocumentField(RohonAccount)
    date_time = DateTimeField()
