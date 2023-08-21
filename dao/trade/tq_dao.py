from dao.odm.tq_odm import (TqOrder)
from utils.tqsdk_tools import (
    get_chinadt_from_ns
)
from tqsdk.objs import Order

def createTqOrder(order: Order):
    tq_order = TqOrder()
    tq_order.order_id = order.order_id
    tq_order.exchange_id = order.exchange_id
    tq_order.exchange_order_id = order.exchange_order_id
    tq_order.instrument_id = order.instrument_id
    tq_order.direction = order.direction
    tq_order.offset = order.offset
    tq_order.volume_orign = order.volume_orign
    tq_order.volume_left = order.volume_left
    tq_order.limit_price = order.limit_price
    tq_order.price_type = order.price_type
    tq_order.volume_condition = order.volume_condition
    tq_order.time_condition = order.time_condition
    tq_order.insert_date_time = get_chinadt_from_ns(order.insert_date_time)
    tq_order.last_msg = order.last_msg
    tq_order.status = order.status
    tq_order.is_error = order.is_error
    tq_order.trade_price = order.trade_price
    tq_order.save()

