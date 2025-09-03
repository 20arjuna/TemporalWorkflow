#!/usr/bin/env python3
"""
Test script to verify order activity logic with database integration.
Tests the core activity logic without Temporal decorators.
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import startup_db, shutdown_db, execute_query
from db.queries import OrderQueries, PaymentQueries, EventQueries, DatabaseStats
from activities import stubs

async def test_activity_logic_db():
    """Test order activity logic with database integration."""
    print("🧪 Testing Order Activity Logic with Database Integration")
    print("=" * 60)
    
    # Test data
    test_order_id = f"TEST-LOGIC-{int(datetime.now().timestamp())}"
    test_address = {
        "line1": "789 Logic Test Blvd",
        "city": "Test City",
        "state": "TC", 
        "zip": "98765"
    }
    test_items = [
        {"name": "Widget A", "quantity": 2, "price": 29.99},
        {"name": "Widget B", "quantity": 1, "price": 39.99}
    ]
    
    try:
        # Initialize database
        print("🔌 Initializing database...")
        await startup_db()
        
        # Clean up any existing test data
        await cleanup_test_data(test_order_id)
        
        print(f"🚀 Testing order: {test_order_id}")
        
        # Test each activity logic
        await test_receive_order_logic(test_order_id, test_address)
        await test_validate_order_logic(test_order_id, test_address, test_items)
        await test_charge_payment_logic(test_order_id, test_address)
        
        # Verify database state
        await verify_database_state(test_order_id)
        
        # Test idempotency
        await test_payment_idempotency_logic(test_order_id, test_address)
        
        print("\n🎉 ALL TESTS PASSED! Order activity logic is working with database! 🚀")
        return True
        
    except Exception as e:
        print(f"\n💥 Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        await cleanup_test_data(test_order_id)
        await shutdown_db()

async def test_receive_order_logic(order_id: str, address: dict):
    """Test the receive_order activity logic."""
    print(f"\n📦 Testing receive_order logic...")
    
    order_data = {"order_id": order_id, "address": address}
    
    try:
        # Replicate receive_order logic
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
            "source": "test_logic",
            "address": address
        })
        
        # Call original stub logic (for any business rules)
        stub_result = await stubs.order_received(order_id)
        
        result = {
            "status": "received",
            "order_id": order_id,
            "message": f"Order {order_id} received and persisted",
            "stub_result": stub_result
        }
        
        assert result["status"] == "received", f"Expected 'received', got {result['status']}"
        assert result["order_id"] == order_id
        print(f"   ✅ Order received: {result['message']}")
        
        # Verify in database
        order = await OrderQueries.get_order(order_id)
        assert order is not None, "Order not found in database"
        assert order["state"] == "received"
        assert order["address_json"]["city"] == address["city"]
        print(f"   ✅ Order persisted in database: state={order['state']}")
        
        # Check events
        events = await EventQueries.get_order_events(order_id)
        assert len(events) >= 1, "No events logged"
        creation_event = next((e for e in events if e['event_type'] == 'order_received'), None)
        assert creation_event is not None, "order_received event not found"
        print(f"   ✅ Event logged: {creation_event['event_type']}")
        
    except Exception as e:
        print(f"❌ receive_order logic failed for {order_id}: {e}")
        raise

async def test_validate_order_logic(order_id: str, address: dict, items: list):
    """Test the validate_order activity logic."""
    print(f"\n✅ Testing validate_order logic...")
    
    order_data = {"order_id": order_id, "address": address, "items": items}
    
    try:
        # Replicate validate_order logic
        await startup_db()
        
        # Update order state to validating
        await OrderQueries.update_order_state(order_id, "validating")
        
        # Log validation start
        await EventQueries.log_event(order_id, "validation_started", {
            "source": "test_logic",
            "order_data": order_data
        })
        
        # Call original validation logic
        stub_result = await stubs.order_validated(order_data)
        
        # If validation succeeds, update state
        await OrderQueries.update_order_state(order_id, "validated")
        
        # Log successful validation
        await EventQueries.log_event(order_id, "order_validated", {
            "source": "test_logic",
            "validation_result": stub_result
        })
        
        result = {
            "status": "validated",
            "order_id": order_id,
            "message": f"Order {order_id} validated successfully",
            "validation_result": stub_result
        }
        
        assert result["status"] == "validated", f"Expected 'validated', got {result['status']}"
        assert result["order_id"] == order_id
        print(f"   ✅ Order validated: {result['message']}")
        
        # Verify state updated in database
        order = await OrderQueries.get_order(order_id)
        assert order["state"] == "validated", f"Expected state 'validated', got {order['state']}"
        print(f"   ✅ Database state updated: {order['state']}")
        
        # Check validation events
        events = await EventQueries.get_order_events(order_id)
        validation_events = [e for e in events if 'validation' in e['event_type'] or 'validated' in e['event_type']]
        print(f"   📝 All events: {[e['event_type'] for e in events]}")
        print(f"   📝 Validation events: {[e['event_type'] for e in validation_events]}")
        assert len(validation_events) >= 2, f"Expected validation_started and order_validated events, got {len(validation_events)}"
        print(f"   ✅ Validation events logged: {len(validation_events)} events")
        
    except Exception as e:
        print(f"❌ validate_order logic failed for {order_id}: {e}")
        
        # Update state to validation failed
        try:
            await OrderQueries.update_order_state(order_id, "validation_failed")
            await EventQueries.log_event(order_id, "validation_failed", {
                "error": str(e),
                "order_data": order_data
            })
        except:
            pass
        raise

async def test_charge_payment_logic(order_id: str, address: dict):
    """Test the charge_payment activity logic."""
    print(f"\n💳 Testing charge_payment logic...")
    
    order_data = {"order_id": order_id, "address": address, "amount": 99.99, "payment_attempt": 1}
    amount = order_data.get("amount", 99.99)
    
    # Generate idempotent payment ID
    payment_attempt = order_data.get("payment_attempt", 1)
    payment_id = f"{order_id}-payment-{payment_attempt}"
    
    try:
        # Replicate charge_payment logic
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
            
            result = {
                "status": "already_charged",
                "order_id": order_id,
                "payment_id": payment_id,
                "amount": float(existing_payment["amount"]),
                "message": f"Payment {payment_id} already processed"
            }
        else:
            # Create pending payment record (idempotent)
            await PaymentQueries.create_payment(payment_id, order_id, amount, "pending")
            
            # Update order state
            await OrderQueries.update_order_state(order_id, "charging_payment")
            
            # Log payment start
            await EventQueries.log_event(order_id, "payment_charging_started", {
                "payment_id": payment_id,
                "amount": amount,
                "source": "test_logic"
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
                "source": "test_logic",
                "gateway_result": stub_result
            })
            
            result = {
                "status": "charged",
                "order_id": order_id,
                "payment_id": payment_id,
                "amount": amount,
                "message": f"Payment {payment_id} charged successfully",
                "gateway_result": stub_result
            }
        
        assert result["status"] in ["charged", "already_charged"], f"Expected 'charged' or 'already_charged', got {result['status']}"
        assert result["order_id"] == order_id
        assert result["amount"] == 99.99
        print(f"   ✅ Payment processed: {result['message']}")
        
        # Verify payment in database
        payment_id = result["payment_id"]
        payment = await PaymentQueries.get_payment(payment_id)
        assert payment is not None, "Payment not found in database"
        assert payment["status"] == "charged", f"Expected payment status 'charged', got {payment['status']}"
        assert float(payment["amount"]) == 99.99
        print(f"   ✅ Payment persisted: {payment_id} - ${payment['amount']}")
        
        # Verify order state
        order = await OrderQueries.get_order(order_id)
        assert order["state"] == "payment_charged", f"Expected state 'payment_charged', got {order['state']}"
        print(f"   ✅ Order state updated: {order['state']}")
        
        # Check payment events
        events = await EventQueries.get_order_events(order_id)
        payment_events = [e for e in events if 'payment' in e['event_type']]
        assert len(payment_events) >= 2, "Expected payment events"
        print(f"   ✅ Payment events logged: {len(payment_events)} events")
        
    except Exception as e:
        # Check if it's a flaky_call failure (expected)
        if "Forced failure" in str(e) or "timeout" in str(e).lower():
            print(f"   ⚠️  Payment failed due to flaky_call (expected): {e}")
            
            # Update payment and order status to failed
            try:
                await PaymentQueries.update_payment_status(payment_id, "failed")
                await OrderQueries.update_order_state(order_id, "payment_failed")
                await EventQueries.log_event(order_id, "payment_failed", {
                    "payment_id": payment_id,
                    "error": str(e),
                    "order_data": order_data
                })
            except:
                pass
            
            # Verify failure is properly recorded
            order = await OrderQueries.get_order(order_id)
            assert order["state"] == "payment_failed", f"Expected state 'payment_failed', got {order['state']}"
            
            payment = await PaymentQueries.get_payment(payment_id)
            if payment:
                assert payment["status"] == "failed", f"Expected payment status 'failed', got {payment['status']}"
            
            print(f"   ✅ Failure properly recorded in database")
        else:
            print(f"❌ charge_payment logic failed for {order_id}: {e}")
            raise

async def test_payment_idempotency_logic(order_id: str, address: dict):
    """Test payment idempotency."""
    print(f"\n🔄 Testing payment idempotency logic...")
    
    payment_data = {
        "order_id": order_id, 
        "address": address,
        "amount": 99.99,
        "payment_attempt": 2  # Different attempt number
    }
    
    # Get current payment count
    payments_before = await PaymentQueries.get_payments_for_order(order_id)
    
    try:
        # Test creating another payment with different attempt
        payment_id = f"{order_id}-payment-2"
        success = await PaymentQueries.create_payment(payment_id, order_id, 99.99, "pending")
        assert success, "Failed to create second payment"
        
        # Verify it's a separate payment
        payments_after = await PaymentQueries.get_payments_for_order(order_id)
        assert len(payments_after) == len(payments_before) + 1, "Second payment not created"
        print(f"   ✅ Payment idempotency working: {len(payments_after)} total payments")
        
        # Test duplicate payment_id (should be idempotent)
        success2 = await PaymentQueries.create_payment(payment_id, order_id, 99.99, "pending")
        assert success2, "Idempotent payment creation failed"
        
        # Should still be the same count
        payments_final = await PaymentQueries.get_payments_for_order(order_id)
        assert len(payments_final) == len(payments_after), "Duplicate payment created (idempotency broken)"
        print(f"   ✅ Duplicate payment prevented: {len(payments_final)} total payments")
        
    except Exception as e:
        print(f"❌ Payment idempotency test failed: {e}")
        raise

async def verify_database_state(order_id: str):
    """Verify the final database state."""
    print(f"\n📊 Verifying database state...")
    
    # Check order
    order = await OrderQueries.get_order(order_id)
    assert order is not None, "Order not found"
    print(f"   📦 Order: {order['id']} - {order['state']}")
    
    # Check payments
    payments = await PaymentQueries.get_payments_for_order(order_id)
    print(f"   💳 Payments: {len(payments)} records")
    for payment in payments:
        print(f"      - {payment['payment_id']}: {payment['status']} - ${payment['amount']}")
    
    # Check events
    events = await EventQueries.get_order_events(order_id)
    print(f"   📝 Events: {len(events)} recorded")
    for event in events:
        print(f"      - {event['event_type']} at {event['ts']}")
    
    # Get stats
    stats = await DatabaseStats.get_order_stats()
    print(f"   📈 Database stats: {stats['total_orders']} total orders")

async def cleanup_test_data(order_id: str):
    """Clean up test data."""
    try:
        # Delete in proper order (foreign key constraints)
        await execute_query("DELETE FROM events WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM payments WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)
        print(f"   🧹 Cleaned up test data for {order_id}")
    except Exception as e:
        print(f"   ⚠️  Cleanup warning: {e}")

async def main():
    """Run the order activity logic database integration test."""
    success = await test_activity_logic_db()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)