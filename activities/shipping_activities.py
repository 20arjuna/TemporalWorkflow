"""
Shipping-related activities.
"""
from . import stubs
from temporalio import activity

@activity.defn
async def prepare_package(order: dict):
    """Prepare a package for shipping."""
    return await stubs.package_prepared(order)

@activity.defn
async def dispatch_carrier(order: dict):
    """Dispatch the carrier for delivery."""
    return await stubs.carrier_dispatched(order)
