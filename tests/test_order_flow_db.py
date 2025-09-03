#!/usr/bin/env python3
"""
Test script to verify order workflow integration with database.
Tests the complete order flow with database persistence.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from temporalio.client import Client
from temporalio.worker import Worker
from workflows.order_workflow import OrderWorkflow
from activities.order_activities import receive_order, validate_order, charge_payment
from db.connection import startup_db, shutdown_db
from db.queries import OrderQueries, PaymentQueries, EventQueries, DatabaseStats

async def test_single_order_flow():
    """Test a complete order flow with database integration."""
    print("🧪 Testing Order Flow with Database Integration")
    print("=" * 60)
    
    # Test data
    test_order_id = f"TEST-DB-ORDER-{int(datetime.now().timestamp())}"
    test_address = {
        "line1": "789 Database Test Blvd",
        "city": "Test City",
        "state": "TC", 
        "zip": "98765"
    }
    
    try:
        # Initialize database
        print("🔌 Initializing database...")
        await startup_db()
        
        # Clean up any existing test data
        await cleanup_test_data(test_order_id)
        
        print(f"🚀 Testing order: {test_order_id}")
        
        # Test each activity individually first
        await test_receive_order_activity(test_order_id, test_address)
        await test_validate_order_activity(test_order_id, test_address)
        await test_charge_payment_activity(test_order_id, test_address)
        
        # Verify database state
        await verify_database_state(test_order_id)
        
        # Test idempotency
        await test_payment_idempotency(test_order_id, test_address)
        
        print("\n🎉 ALL TESTS PASSED! Order flow is working with database! 🚀")
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

async def test_receive_order_activity(order_id: str, address: dict):
    """Test the receive_order activity."""
    print(f"\n📦 Testing receive_order activity...")
    
    order_data = {"order_id": order_id, "address": address}
    result = await receive_order(order_data)
    
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

async def test_validate_order_activity(order_id: str, address: dict):
    """Test the validate_order activity."""
    print(f"\n✅ Testing validate_order activity...")
    
    order_data = {"order_id": order_id, "address": address}
    result = await validate_order(order_data)
    
    assert result["status"] == "validated", f"Expected 'validated', got {result['status']}"
    assert result["order_id"] == order_id
    print(f"   ✅ Order validated: {result['message']}")
    
    # Verify state updated in database
    order = await OrderQueries.get_order(order_id)
    assert order["state"] == "validated", f"Expected state 'validated', got {order['state']}"
    print(f"   ✅ Database state updated: {order['state']}")
    
    # Check validation events
    events = await EventQueries.get_order_events(order_id)
    validation_events = [e for e in events if 'validation' in e['event_type']]
    assert len(validation_events) >= 2, "Expected validation_started and order_validated events"
    print(f"   ✅ Validation events logged: {len(validation_events)} events")

async def test_charge_payment_activity(order_id: str, address: dict):
    """Test the charge_payment activity."""
    print(f"\n💳 Testing charge_payment activity...")
    
    payment_data = {
        "order_id": order_id, 
        "address": address,
        "amount": 99.99,
        "payment_attempt": 1
    }
    
    try:
        result = await charge_payment(payment_data)
        
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
            
            # Verify failure is properly recorded
            order = await OrderQueries.get_order(order_id)
            assert order["state"] == "payment_failed", f"Expected state 'payment_failed', got {order['state']}"
            
            payment_id = f"{order_id}-payment-1"
            payment = await PaymentQueries.get_payment(payment_id)
            if payment:
                assert payment["status"] == "failed", f"Expected payment status 'failed', got {payment['status']}"
            
            print(f"   ✅ Failure properly recorded in database")
        else:
            raise

async def test_payment_idempotency(order_id: str, address: dict):
    """Test payment idempotency."""
    print(f"\n🔄 Testing payment idempotency...")
    
    payment_data = {
        "order_id": order_id, 
        "address": address,
        "amount": 99.99,
        "payment_attempt": 2  # Different attempt number
    }
    
    # Get current payment count
    payments_before = await PaymentQueries.get_payments_for_order(order_id)
    
    try:
        result = await charge_payment(payment_data)
        
        # Check that we didn't create duplicate payments
        payments_after = await PaymentQueries.get_payments_for_order(order_id)
        
        # Should have one more payment (different attempt number)
        assert len(payments_after) == len(payments_before) + 1, "Payment not idempotent correctly"
        print(f"   ✅ Payment idempotency working: {len(payments_after)} total payments")
        
    except Exception as e:
        if "Forced failure" in str(e) or "timeout" in str(e).lower():
            print(f"   ⚠️  Second payment failed due to flaky_call (acceptable)")
        else:
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
        await EventQueries.log_event(order_id, "test_cleanup", {"source": "test_script"})
        # Note: We don't actually delete to preserve test data for inspection
        # In a real test, you might want to clean up
    except:
        pass

async def main():
    """Run the order flow database integration test."""
    success = await test_single_order_flow()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)