from datetime import date, datetime
from typing import List

from mongoengine import (
    BooleanField,
    DateField,
    DateTimeField,
    Document,
    EmbeddedDocument,
    EmbeddedDocumentField,
    EmbeddedDocumentListField,
    FloatField,
    IntField,
    ListField,
    StringField,
)


class SymbolList(EmbeddedDocument):
    current_symbol: str = StringField()
    next_symbol: str = StringField()


class InvolvedSymbol(EmbeddedDocument):
    mj_symbol: str = StringField()
    long_symbols: SymbolList = EmbeddedDocumentField(SymbolList)
    short_symbols: SymbolList = EmbeddedDocumentField(SymbolList)


class TradeRecord(Document):
    trade_date: date = DateField(required=True, unique=True)
    current_balance: float = FloatField()
    start_time: datetime = DateTimeField()
    end_time: datetime = DateTimeField()
    run_times: int = IntField(default=0)
    has_run_pre_opt: bool = BooleanField(default=False)
    has_trade: bool = BooleanField(default=False)
    has_run_post_opt: bool = BooleanField(default=False)
    config_mj_symbols: List[str] = ListField(StringField())
    involved_main_symbols: List[InvolvedSymbol] = EmbeddedDocumentListField(
        InvolvedSymbol
    )
