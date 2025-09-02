"""
Stub implementations for activities.
These are placeholder functions that the tests expect to exist.
"""

async def flaky_call():
    """Placeholder for a flaky external call."""
    pass

async def order_received(order_id: str):
    """Stub for order received activity."""
    return {
        "order_id": order_id,
        "items": []
    }

async def order_validated(order: dict):
    """Stub for order validation activity."""
    return True

async def package_prepared(order: dict):
    """Stub for package preparation activity."""
    return "Package ready"