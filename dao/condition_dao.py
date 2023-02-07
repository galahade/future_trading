from pymongo.database import Database
import hashlib
from dao.condition_entity import BottomConditionInfo


db: Database = None


def store_bottom_condition_info(bci: BottomConditionInfo) -> None:
    key = bci.custom_symbol + bci.symbol + bci.datetime.strftime("%Y-%m-%d")
    key_hash = hashlib.sha1(key.encode()).hexdigest()
    dict_data = {
        '_id': key_hash,
        'custom_symbol': bci.custom_symbol,
        'symbol': bci.symbol,
        'datetime': bci.datetime,
        'last_price': bci.last_price,
        'pos': bci.pos,
        'balance': bci.balance,
        'open_pos_scale': bci.open_pos_scale,
        'contract_m': bci.contract_m,
        'day_condition': {
            'ema5': bci.day_condition.ema5,
            'ema20': bci.day_condition.ema20,
            'ema60': bci.day_condition.ema60,
            'macd': bci.day_condition.macd,
            'condition_time': bci.day_condition.condition_time
        },
        'hours_condition': {
            'ema5': bci.hours_condition.ema5,
            'ema20': bci.hours_condition.ema20,
            'ema60': bci.hours_condition.ema60,
            'macd': bci.hours_condition.macd,
            'condition_time': bci.hours_condition.condition_time
        },
        'minutes_condition': {
            'ema5': bci.minutes_condition.ema5,
            'ema20': bci.minutes_condition.ema20,
            'ema60': bci.minutes_condition.ema60,
            'macd': bci.minutes_condition.macd,
            'condition_time': bci.minutes_condition.condition_time
        }
    }
    db.bottom_condition_infos.update_one(
        {'_id': key_hash}, {'$set': dict_data}, upsert=True)
