"""
Stub implementations for activities.
These are placeholder functions that the tests expect to exist.
"""

from typing import Dict, Any
import asyncio, random

async def flaky_call() -> None:
    """Either raise an error or sleep long enough to trigger an activity timeout."""
    rand_num = random.random()
    if rand_num < 0.33:  # 15% chance of immediate failure
        print("Raising RuntimeError for testing")
        raise RuntimeError("Forced failure for testing")

    if rand_num < 0.67:  # 10% chance of timeout (25% - 15% = 10%)
        print("Sleeping for 5 seconds to trigger timeout")
        await asyncio.sleep(5)  # Sleep longer than 10s activity timeout to trigger timeout

    # 75% chance of success (no sleep, no error)

async def order_received(order_id: str) -> Dict[str, Any]:
    await flaky_call()
    # TODO: Implement DB write: insert new order record
    return {"order_id": order_id, "items": [{"sku": "ABC", "qty": 1}]}

async def order_validated(order: Dict[str, Any]) -> bool:
    await flaky_call()
    # TODO: Implement DB read/write: fetch order, update validation status
    if not order.get("items"):
        raise ValueError("No items to validate")
    return True

async def payment_charged(order: Dict[str, Any], payment_id: str, db) -> Dict[str, Any]:
    """Charge payment after simulating an error/timeout first.
    You must implement your own idempotency logic in the activity or here.
    """
    await flaky_call()
    # TODO: Implement DB read/write: check payment record, insert/update payment status
    amount = sum(i.get("qty", 1) for i in order.get("items", []))
    return {"status": "charged", "amount": amount}

async def order_shipped(order: Dict[str, Any]) -> str:
    await flaky_call()
    # TODO: Implement DB write: update order status to shipped
    return "Shipped"

async def package_prepared(order: Dict[str, Any]) -> str:
    await flaky_call()
    # TODO: Implement DB write: mark package prepared in DB
    return "Package ready"

async def carrier_dispatched(order: Dict[str, Any]) -> str:
    await flaky_call()
    # TODO: Implement DB write: record carrier dispatch status
    return "Dispatched"