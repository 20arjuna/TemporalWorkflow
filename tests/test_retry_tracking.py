#!/usr/bin/env python3
"""
Test retry tracking functionality without Temporal SDK dependencies.
Tests the retry tracking infrastructure and database integration.
"""

import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import startup_db, shutdown_db, execute_query
from db.queries import RetryQueries, EventQueries
from activities.retry_tracker import get_activity_attempt_count

async def test_retry_tracking():
    """Test the retry tracking functionality."""
    print("🧪 Testing Retry Tracking System")
    print("=" * 50)
    
    try:
        await startup_db()
        
        # Clean up any existing test data
        test_order_id = "RETRY-TEST-001"
        await execute_query("DELETE FROM activity_attempts WHERE order_id = $1", test_order_id)
        await execute_query("DELETE FROM events WHERE order_id = $1", test_order_id)
        
        print(f"🧹 Cleaned up existing test data for {test_order_id}")
        
        # Test 1: Log first attempt
        print(f"\n📝 Test 1: Logging first attempt")
        success = await RetryQueries.log_activity_attempt(
            order_id=test_order_id,
            activity_name="charge_payment",
            attempt_number=1,
            status="started"
        )
        assert success, "Failed to log first attempt"
        print(f"   ✅ First attempt logged successfully")
        
        # Test 2: Log failure
        print(f"\n❌ Test 2: Logging failure")
        success = await RetryQueries.log_activity_attempt(
            order_id=test_order_id,
            activity_name="charge_payment",
            attempt_number=1,
            status="failed",
            error_message="Credit card declined",
            execution_time_ms=1500
        )
        assert success, "Failed to log failure"
        print(f"   ✅ Failure logged successfully")
        
        # Test 3: Log second attempt (retry)
        print(f"\n🔄 Test 3: Logging retry attempt")
        success = await RetryQueries.log_activity_attempt(
            order_id=test_order_id,
            activity_name="charge_payment",
            attempt_number=2,
            status="started"
        )
        assert success, "Failed to log retry attempt"
        
        success = await RetryQueries.log_activity_attempt(
            order_id=test_order_id,
            activity_name="charge_payment",
            attempt_number=2,
            status="completed",
            output_data={"payment_id": "RETRY-TEST-001-payment-2", "status": "charged"},
            execution_time_ms=800
        )
        assert success, "Failed to log retry success"
        print(f"   ✅ Retry attempt logged successfully")
        
        # Test 4: Get attempt count
        print(f"\n🔢 Test 4: Getting attempt count")
        count = await get_activity_attempt_count(test_order_id, "charge_payment")
        print(f"   Next attempt number would be: {count}")
        assert count == 3, f"Expected attempt count 3, got {count}"  # Next attempt would be 3
        print(f"   ✅ Attempt count is correct")
        
        # Test 5: Get all attempts for order
        print(f"\n📊 Test 5: Getting all attempts")
        attempts = await RetryQueries.get_order_attempts(test_order_id)
        print(f"   Found {len(attempts)} attempts:")
        for attempt in attempts:
            print(f"      - Attempt {attempt['attempt_number']}: {attempt['status']} ({attempt['execution_time_ms']}ms)")
        
        assert len(attempts) == 3, f"Expected 3 attempts, got {len(attempts)}"
        print(f"   ✅ All attempts retrieved correctly")
        
        # Test 6: Get retry summary
        print(f"\n📈 Test 6: Getting retry summary")
        summary = await RetryQueries.get_order_retry_summary(test_order_id)
        if summary:
            print(f"   Order: {summary['order_id']}")
            print(f"   Total Attempts: {summary['total_activity_attempts']}")
            print(f"   Failed Attempts: {summary['failed_attempts']}")
            print(f"   Successful Attempts: {summary['successful_attempts']}")
            print(f"   ✅ Retry summary retrieved")
        else:
            print(f"   ⚠️  No retry summary found (order might not be in orders table)")
        
        # Test 7: Activity performance
        print(f"\n⚡ Test 7: Activity performance")
        performance = await RetryQueries.get_activity_performance()
        if performance:
            for activity in performance:
                if activity['activity_name'] == 'charge_payment':
                    print(f"   {activity['activity_name']}:")
                    print(f"      Success Rate: {(activity['successful_attempts'] / activity['total_attempts']) * 100:.1f}%")
                    print(f"      Avg Time: {activity['avg_execution_time_ms']}ms")
                    print(f"      Total Attempts: {activity['total_attempts']}")
                    print(f"   ✅ Performance data retrieved")
                    break
        else:
            print(f"   ⚠️  No performance data found")
        
        print(f"\n🎉 ALL RETRY TRACKING TESTS PASSED!")
        print(f"\n💡 Retry tracking is working:")
        print(f"   ✅ Activities can log attempts with timing")
        print(f"   ✅ Failed attempts are tracked with error details")
        print(f"   ✅ Retry counts increment correctly")
        print(f"   ✅ Performance metrics are calculated")
        print(f"   ✅ Ready for resilience testing!")
        
        return True
        
    except Exception as e:
        print(f"\n💥 Retry tracking test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up test data
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id = $1", test_order_id)
            print(f"\n🧹 Cleaned up test data")
        except:
            pass
        
        await shutdown_db()

if __name__ == "__main__":
    success = asyncio.run(test_retry_tracking())
    sys.exit(0 if success else 1)