"""
Order-related activities with database integration.
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
async def receive_order(order_id: str, address: dict) -> Dict[str, Any]:
    """Receive and process an order with database persistence."""
    # Simple retry tracking using Temporal's retry info
    from temporalio import activity
    info = activity.info()
    attempt_number = info.attempt if info else 1
    
    try:
        # Ensure database is initialized
        await startup_db()
        
        # Create order in database
        success = await OrderQueries.create_order(order_id, address, "received")
        if not success:
            # Check if order already exists (idempotency)
            existing = await OrderQueries.get_order(order_id)
            if not existing:
                raise Exception(f"Failed to create order {order_id}")
        
        # Log event
        await EventQueries.log_event(order_id, "order_received", {
            "source": "temporal_activity",
            "address": address,
            "attempt_number": attempt_number
        })
        
        # Call original stub logic (for any business rules)
        stub_result = await stubs.order_received(order_id)
        
        return {
            "status": "received",
            "order_id": order_id,
            "message": f"Order {order_id} received and persisted",
            "stub_result": stub_result
        }
        
    except Exception as e:
        print(f"❌ receive_order failed for {order_id}: {e}")
        
        # Log failure event
        try:
            await EventQueries.log_event(order_id, "order_receive_failed", {
                "error": str(e),
                "attempt_number": attempt_number,
                "order_id": order_id,
                "address": address
            })
        except:
            pass  # Don't fail the activity if event logging fails
        
        raise

@activity.defn
async def validate_order(order_id: str, address: dict, items: list = None) -> Dict[str, Any]:
    """Validate an order with database state tracking."""
    # Simple retry tracking using Temporal's retry info
    from temporalio import activity
    info = activity.info()
    attempt_number = info.attempt if info else 1
    
    # Reconstruct order_data for stub compatibility
    order_data = {"order_id": order_id, "address": address, "items": items or []}
    
    try:
        # Ensure database is initialized
        await startup_db()
        
        # Update order state to validating
        await OrderQueries.update_order_state(order_id, "validating")
        
        # Log validation start
        await EventQueries.log_event(order_id, "validation_started", {
            "source": "temporal_activity",
            "attempt_number": attempt_number,
            "order_id": order_id,
            "address": address,
            "items": items
        })
        
        # Call original validation logic (this may throw for business rule failures)
        stub_result = await stubs.order_validated(order_data)
        
        # If validation succeeds, update state
        await OrderQueries.update_order_state(order_id, "validated")
        
        # Log successful validation
        await EventQueries.log_event(order_id, "order_validated", {
            "source": "temporal_activity",
            "attempt_number": attempt_number,
            "validation_result": stub_result
        })
        
        return {
            "status": "validated",
            "order_id": order_id,
            "message": f"Order {order_id} validated successfully",
            "validation_result": stub_result
        }
        
    except Exception as e:
        print(f"❌ validate_order failed for {order_id}: {e}")
        
        # Update state to validation failed
        try:
            await OrderQueries.update_order_state(order_id, "validation_failed")
            await EventQueries.log_event(order_id, "validation_failed", {
                "error": str(e),
                "attempt_number": attempt_number,
                "order_id": order_id,
                "address": address,
                "items": items
            })
        except:
            pass  # Don't fail the activity if DB update fails
        
        raise

@activity.defn
async def charge_payment(order_id: str, address: dict, amount: float = 99.99) -> Dict[str, Any]:
    """Charge payment for an order with idempotent database persistence."""
    # Simple retry tracking using Temporal's retry info
    from temporalio import activity
    info = activity.info()
    attempt_number = info.attempt if info else 1
    
    # Generate idempotent payment ID (order_id + attempt number)
    payment_id = f"{order_id}-payment-{attempt_number}"
    
    try:
        # Ensure database is initialized
        await startup_db()
        
        # Check if payment already processed (idempotency)
        is_processed = await PaymentQueries.is_payment_processed(payment_id)
        if is_processed:
            # Payment already processed, return existing result
            existing_payment = await PaymentQueries.get_payment(payment_id)
            await EventQueries.log_event(order_id, "payment_already_processed", {
                "payment_id": payment_id,
                "status": existing_payment["status"]
            })
            
            return {
                "status": "already_charged",
                "order_id": order_id,
                "payment_id": payment_id,
                "amount": float(existing_payment["amount"]),
                "message": f"Payment {payment_id} already processed"
            }
        
        # Create pending payment record (idempotent)
        await PaymentQueries.create_payment(payment_id, order_id, amount, "pending")
        
        # Update payment retry info if this is a retry
        if attempt_number > 1:
            await PaymentQueries.update_payment_retry_info(
                payment_id=payment_id,
                attempt_number=attempt_number,
                retry_count=attempt_number - 1
            )
        
        # Update order state
        await OrderQueries.update_order_state(order_id, "charging_payment")
        
        # Log payment start
        await EventQueries.log_event(order_id, "payment_charging_started", {
            "payment_id": payment_id,
            "amount": amount,
            "source": "temporal_activity"
        })
        
        # Call original payment logic (this handles the actual payment processing)
        stub_result = await stubs.flaky_call()  # This simulates payment gateway call
        
        # Update payment status to charged
        await PaymentQueries.update_payment_status(payment_id, "charged")
        await OrderQueries.update_order_state(order_id, "payment_charged")
        
        # Log successful payment
        await EventQueries.log_event(order_id, "payment_charged", {
            "payment_id": payment_id,
            "amount": amount,
            "source": "temporal_activity",
            "gateway_result": stub_result
        })
        
        return {
            "status": "charged",
            "order_id": order_id,
            "payment_id": payment_id,
            "amount": amount,
            "message": f"Payment {payment_id} charged successfully",
            "gateway_result": stub_result
        }
        
    except Exception as e:
        print(f"❌ charge_payment failed for {order_id}: {e}")
        
        # Update payment and order status to failed
        try:
            await PaymentQueries.update_payment_status(payment_id, "failed")
            # Update retry info with error
            await PaymentQueries.update_payment_retry_info(
                payment_id=payment_id,
                attempt_number=attempt_number,
                retry_count=attempt_number - 1,
                last_error=str(e)
            )
            await OrderQueries.update_order_state(order_id, "payment_failed")
            await EventQueries.log_event(order_id, "payment_failed", {
                "payment_id": payment_id,
                "error": str(e),
                "attempt_number": attempt_number,
                "retry_count": attempt_number - 1,
                "order_id": order_id,
                "address": address,
                "amount": amount
            })
        except:
            pass  # Don't fail the activity if DB update fails
        
        raise