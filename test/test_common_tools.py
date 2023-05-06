from datetime import datetime
from utils.common_tools import (
    get_china_date_from_str, get_next_symbol, tz_utc_8
)


class TestClass:

    def test_get_next_symbol(self):
        next_symbol = get_next_symbol('DCE.a2305', [1, 5, 9])
        assert next_symbol == 'DCE.a2309'
        next_symbol = get_next_symbol('DCE.a2309', [1, 5, 9])
        assert next_symbol == 'DCE.a2401'

    def test_get_datetime_from_str(self):
        date = get_china_date_from_str('2021-01-01 00:00:00.000000')
        assert date == datetime(2021, 1, 1, 0, 0, 0, 0, tzinfo=tz_utc_8)
