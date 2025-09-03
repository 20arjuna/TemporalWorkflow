#!/usr/bin/env python3
"""
Simple test script for database connection layer.
Tests connection pooling, query functions, and basic operations.
"""

import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import DatabaseManager, startup_db, shutdown_db, execute_query
from db.queries import OrderQueries, PaymentQueries, EventQueries, DatabaseStats

async def test_connection_health():
    """Test basic database health check."""
    print("🧪 Testing database health...")
    
    health = await DatabaseManager.health_check()
    print(f"📊 Health Status: {health['status']}")
    
    if health['status'] == 'healthy':
        print(f"   PostgreSQL Version: {health['version'][:50]}...")
        print(f"   Pool Size: {health['pool_size']} (Idle: {health['pool_idle']})")
        print(f"   Table Counts: {health['table_counts']}")
        return True
    else:
        print(f"   Error: {health.get('error', 'Unknown error')}")
        return False

async def test_order_operations():
    """Test order CRUD operations."""
    print("\n🛒 Testing order operations...")
    
    test_order_id = "TEST-CONN-ORDER"
    test_address = {
        "line1": "456 Connection Test Ave",
        "city": "Test City",
        "state": "TC",
        "zip": "54321"
    }
    
    try:
        # Clean up any existing test data first
        existing = await OrderQueries.get_order(test_order_id)
        if existing:
            print(f"   🧹 Cleaning up existing test order...")
            await execute_query("DELETE FROM events WHERE order_id = $1", test_order_id)
            await execute_query("DELETE FROM payments WHERE order_id = $1", test_order_id)
            await execute_query("DELETE FROM orders WHERE id = $1", test_order_id)
        
        # 1. Create order
        success = await OrderQueries.create_order(test_order_id, test_address)
        assert success, "Failed to create order"
        print(f"   ✅ Created order: {test_order_id}")
        
        # 2. Get order
        order = await OrderQueries.get_order(test_order_id)
        assert order is not None, "Order not found after creation"
        assert order['id'] == test_order_id
        assert order['state'] == 'pending'
        assert order['address_json']['city'] == 'Test City'
        print(f"   ✅ Retrieved order: {order['id']} - {order['state']}")
        
        # 3. Update state
        success = await OrderQueries.update_order_state(test_order_id, 'approved')
        assert success, "Failed to update order state"
        
        updated_order = await OrderQueries.get_order(test_order_id)
        assert updated_order['state'] == 'approved'
        print(f"   ✅ Updated state: {updated_order['state']}")
        
        # 4. Update address
        new_address = test_address.copy()
        new_address['line2'] = 'Suite 100'
        success = await OrderQueries.update_order_address(test_order_id, new_address)
        assert success, "Failed to update address"
        
        updated_order = await OrderQueries.get_order(test_order_id)
        assert updated_order['address_json']['line2'] == 'Suite 100'
        print(f"   ✅ Updated address: Added line2")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Order operations failed: {e}")
        return False

async def test_payment_operations():
    """Test payment operations with idempotency."""
    print("\n💳 Testing payment operations...")
    
    test_order_id = "TEST-CONN-ORDER"
    test_payment_id = f"{test_order_id}-payment-1"
    
    try:
        # 1. Create payment (first time)
        success = await PaymentQueries.create_payment(test_payment_id, test_order_id, 99.99, 'pending')
        assert success, "Failed to create payment"
        print(f"   ✅ Created payment: {test_payment_id}")
        
        # 2. Create same payment (idempotent)
        success = await PaymentQueries.create_payment(test_payment_id, test_order_id, 99.99, 'pending')
        assert success, "Failed on idempotent payment creation"
        print(f"   ✅ Idempotent payment creation successful")
        
        # 3. Check only one payment exists
        payments = await PaymentQueries.get_payments_for_order(test_order_id)
        assert len(payments) == 1, f"Expected 1 payment, got {len(payments)}"
        print(f"   ✅ Idempotency verified: {len(payments)} payment record")
        
        # 4. Update payment status
        success = await PaymentQueries.update_payment_status(test_payment_id, 'charged')
        assert success, "Failed to update payment status"
        
        payment = await PaymentQueries.get_payment(test_payment_id)
        assert payment['status'] == 'charged'
        print(f"   ✅ Updated payment status: {payment['status']}")
        
        # 5. Test payment processed check
        is_processed = await PaymentQueries.is_payment_processed(test_payment_id)
        assert is_processed, "Payment should be marked as processed"
        print(f"   ✅ Payment processed check: {is_processed}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Payment operations failed: {e}")
        return False

async def test_event_operations():
    """Test event logging operations."""
    print("\n📝 Testing event operations...")
    
    test_order_id = "TEST-CONN-ORDER"
    
    try:
        # 1. Log events
        events_to_log = [
            ("order_created", {"source": "test", "method": "connection_test"}),
            ("order_approved", {"approver": "test_user", "timestamp": "2024-01-01T12:00:00Z"}),
            ("payment_charged", {"payment_id": f"{test_order_id}-payment-1", "amount": 99.99}),
        ]
        
        for event_type, payload in events_to_log:
            success = await EventQueries.log_event(test_order_id, event_type, payload)
            assert success, f"Failed to log event: {event_type}"
        
        print(f"   ✅ Logged {len(events_to_log)} events")
        
        # 2. Get order events
        events = await EventQueries.get_order_events(test_order_id)
        assert len(events) >= 3, f"Expected at least 3 events, got {len(events)}"
        
        # Verify event content
        creation_event = next((e for e in events if e['event_type'] == 'order_created'), None)
        assert creation_event is not None, "order_created event not found"
        assert creation_event['payload_json']['source'] == 'test'
        print(f"   ✅ Retrieved {len(events)} events for order")
        
        # 3. Get events by type
        payment_events = await EventQueries.get_events_by_type('payment_charged')
        assert len(payment_events) >= 1, "No payment_charged events found"
        print(f"   ✅ Found {len(payment_events)} payment events")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Event operations failed: {e}")
        return False

async def test_stats_and_monitoring():
    """Test database statistics and monitoring."""
    print("\n📊 Testing stats and monitoring...")
    
    try:
        # 1. Order stats
        order_stats = await DatabaseStats.get_order_stats()
        print(f"   📈 Total orders: {order_stats['total_orders']}")
        print(f"   📊 By state: {order_stats['by_state']}")
        
        # 2. Payment stats
        payment_stats = await DatabaseStats.get_payment_stats()
        print(f"   💰 Total payments: {payment_stats['total_payments']}")
        print(f"   💵 Total charged: ${payment_stats['total_charged_amount']}")
        
        # 3. Recent activity
        activity = await DatabaseStats.get_recent_activity(24)
        print(f"   🕒 Last 24h activity:")
        print(f"      New orders: {activity['new_orders']}")
        print(f"      Total events: {activity['total_events']}")
        print(f"      New payments: {activity['new_payments']}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Stats operations failed: {e}")
        return False

async def cleanup_test_data():
    """Clean up test data."""
    print("\n🧹 Cleaning up test data...")
    
    try:
        test_order_id = "TEST-CONN-ORDER"
        test_payment_id = f"{test_order_id}-payment-1"
        
        # Delete in proper order (foreign key constraints)
        await execute_query("DELETE FROM events WHERE order_id = $1", test_order_id)
        await execute_query("DELETE FROM payments WHERE order_id = $1", test_order_id)
        await execute_query("DELETE FROM orders WHERE id = $1", test_order_id)
        
        print("   ✅ Test data cleaned up")
        return True
        
    except Exception as e:
        print(f"   ❌ Cleanup failed: {e}")
        return False

async def main():
    """Run all connection layer tests."""
    print("🚀 Testing Database Connection Layer")
    print("=" * 50)
    
    try:
        # Initialize database
        await startup_db()
        
        # Run tests
        tests = [
            ("Health Check", test_connection_health),
            ("Order Operations", test_order_operations),
            ("Payment Operations", test_payment_operations),
            ("Event Operations", test_event_operations),
            ("Stats & Monitoring", test_stats_and_monitoring),
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = await test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name} crashed: {e}")
                results.append((test_name, False))
        
        # Cleanup
        await cleanup_test_data()
        
        # Summary
        print("\n" + "=" * 50)
        print("📋 TEST SUMMARY:")
        
        passed = 0
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {status} {test_name}")
            if result:
                passed += 1
        
        print(f"\n🎯 Results: {passed}/{len(results)} tests passed")
        
        if passed == len(results):
            print("🎉 ALL TESTS PASSED! Connection layer is ready! 🚀")
            return True
        else:
            print("💥 Some tests failed. Check the output above.")
            return False
        
    except Exception as e:
        print(f"💥 Test suite crashed: {e}")
        return False
    
    finally:
        # Always cleanup
        await shutdown_db()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)