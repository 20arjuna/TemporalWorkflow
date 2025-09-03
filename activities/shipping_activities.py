"""
Shipping-related activities with database integration.
"""
import sys
import os
from typing import Dict, Any

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from . import stubs

from temporalio import activity
from db.connection import startup_db, shutdown_db
from db.queries import OrderQueries, PaymentQueries, EventQueries

@activity.defn
async def prepare_package(order_id: str, address: dict) -> Dict[str, Any]:
    """Prepare a package for shipping with database tracking."""
    # Simple retry tracking using Temporal's retry info
    from temporalio import activity
    info = activity.info()
    attempt_number = info.attempt if info else 1
    
    try:
        # Ensure database is initialized
        await startup_db()
        
        # Update order state to preparing package
        await OrderQueries.update_order_state(order_id, "preparing_package")
        
        # Log package preparation start
        await EventQueries.log_event(order_id, "package_preparation_started", {
            "source": "temporal_shipping_activity",
            "attempt_number": attempt_number,
            "shipping_address": address,
            "order_id": order_id
        })
        
        # Call original package preparation logic (this may involve physical processes)
        order_data = {"order_id": order_id, "address": address}  # Reconstruct for stub compatibility
        stub_result = await stubs.package_prepared(order_data)
        
        # Update order state to package prepared
        await OrderQueries.update_order_state(order_id, "package_prepared")
        
        # Log successful package preparation
        await EventQueries.log_event(order_id, "package_prepared", {
            "source": "temporal_shipping_activity",
            "attempt_number": attempt_number,
            "preparation_result": stub_result,
            "shipping_address": address
        })
        
        return {
            "status": "package_prepared",
            "order_id": order_id,
            "message": f"Package prepared for order {order_id}",
            "shipping_address": address,
            "preparation_result": stub_result
        }
        
    except Exception as e:
        print(f"❌ prepare_package failed for {order_id}: {e}")
        
        # Update state to preparation failed
        try:
            await OrderQueries.update_order_state(order_id, "package_preparation_failed")
            await EventQueries.log_event(order_id, "package_preparation_failed", {
                "error": str(e),
                "order_data": order_data
            })
        except:
            pass  # Don't fail the activity if DB update fails
        
        raise

@activity.defn
async def dispatch_carrier(order_id: str, address: dict) -> Dict[str, Any]:
    """Dispatch the carrier for delivery with database tracking."""
    # Simple retry tracking using Temporal's retry info
    from temporalio import activity
    info = activity.info()
    attempt_number = info.attempt if info else 1
    
    try:
        # Reconstruct order_data for stub compatibility and logging
        order_data = {"order_id": order_id, "address": address}
        
        # Ensure database is initialized
        await startup_db()
        
        # Update order state to dispatching carrier
        await OrderQueries.update_order_state(order_id, "dispatching_carrier")
        
        # Log carrier dispatch start
        await EventQueries.log_event(order_id, "carrier_dispatch_started", {
            "source": "temporal_shipping_activity",
            "delivery_address": address,
            "order_data": order_data
        })
        
        # Call original carrier dispatch logic (this may involve third-party APIs)
        stub_result = await stubs.carrier_dispatched(order_data)
        
        # Update order state to shipped (final state!)
        await OrderQueries.update_order_state(order_id, "shipped")
        
        # Log successful dispatch and shipping
        await EventQueries.log_event(order_id, "order_shipped", {
            "source": "temporal_shipping_activity",
            "dispatch_result": stub_result,
            "delivery_address": address,
            "tracking_info": stub_result  # stub_result might contain tracking numbers
        })
        
        return {
            "status": "shipped",
            "order_id": order_id,
            "message": f"Order {order_id} shipped successfully",
            "delivery_address": address,
            "dispatch_result": stub_result,
            "tracking_info": stub_result
        }
        
    except Exception as e:
        print(f"❌ dispatch_carrier failed for {order_id}: {e}")
        
        # Update state to dispatch failed
        try:
            await OrderQueries.update_order_state(order_id, "carrier_dispatch_failed")
            await EventQueries.log_event(order_id, "carrier_dispatch_failed", {
                "error": str(e),
                "order_data": order_data
            })
        except:
            pass  # Don't fail the activity if DB update fails
        
        raise
