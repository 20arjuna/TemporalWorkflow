"""
Order-related activities.
"""
from . import stubs

async def receive_order(order_id: str):
    """Receive and process an order."""
    return await stubs.order_received(order_id)