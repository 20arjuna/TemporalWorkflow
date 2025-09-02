"""
Order-related activities.
"""
from . import stubs
from temporalio import activity

@activity.defn

async def receive_order(order_id: str):
    """Receive and process an order."""
    return await stubs.order_received(order_id)

@activity.defn
async def validate_order(order: dict):
    """Validate an order."""
    return await stubs.order_validated(order)

@activity.defn
async def charge_payment(order: dict):
    """Charge payment for an order."""
    # Placeholder for payment processing
    return {"status": "charged", "order_id": order.get("order_id")}