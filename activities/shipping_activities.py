"""
Shipping-related activities.
"""
from . import stubs

async def prepare_package(order: dict):
    """Prepare a package for shipping."""
    return await stubs.package_prepared(order)