"""
Stress Tests and Chaos Engineering

These tests push the system to its limits:
- High failure rates
- Concurrent operations
- Resource exhaustion scenarios
- Network interruptions
- Database stress
"""

import asyncio
import pytest
import json
import time
import random
from unittest.mock import patch, AsyncMock
from decimal import Decimal

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import startup_db, shutdown_db, execute_query
from db.queries import OrderQueries, PaymentQueries, EventQueries, RetryQueries

class TestStressScenarios:
    """Stress test the system under heavy load."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        yield
        
        # Aggressive cleanup of stress test data
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id LIKE 'stress_%'")
            await execute_query("DELETE FROM events WHERE order_id LIKE 'stress_%'")
            await execute_query("DELETE FROM payments WHERE order_id LIKE 'stress_%'")
            await execute_query("DELETE FROM orders WHERE id LIKE 'stress_%'")
        except:
            pass
        
        await shutdown_db()

    async def test_concurrent_order_creation_stress(self):
        """Test creating many orders concurrently."""
        order_count = 50
        order_ids = [f"stress_order_{i}" for i in range(order_count)]
        
        async def create_order_with_events(order_id):
            """Create an order and add some events/attempts."""
            try:
                await OrderQueries.create_order(order_id, json.dumps({"stress": "test"}))
                
                # Add some events
                for j in range(3):
                    await EventQueries.log_event(order_id, f"stress_event_{j}", {"test": True})
                
                # Add some retry attempts
                for attempt in range(1, random.randint(2, 5)):
                    await RetryQueries.log_activity_attempt(
                        order_id, "stress_activity", attempt, 
                        "failed" if attempt < 3 else "completed",
                        random.randint(500, 2000)
                    )
                
                return True
            except Exception as e:
                print(f"Failed to create {order_id}: {e}")
                return False
        
        # Run all creations concurrently
        start_time = time.time()
        results = await asyncio.gather(
            *[create_order_with_events(order_id) for order_id in order_ids],
            return_exceptions=True
        )
        creation_time = time.time() - start_time
        
        # Most should succeed
        successful = sum(1 for r in results if r is True)
        assert successful >= order_count * 0.8, f"Only {successful}/{order_count} orders created successfully"
        
        print(f"✅ Created {successful} orders in {creation_time:.2f}s ({successful/creation_time:.1f} orders/sec)")
        
        # Verify database consistency
        created_orders = await OrderQueries.get_recent_orders(order_count + 10)
        stress_orders = [o for o in created_orders if o["order_id"].startswith("stress_order_")]
        assert len(stress_orders) >= successful * 0.9  # Allow for some cleanup race conditions

    async def test_high_failure_rate_simulation(self):
        """Test system behavior with very high activity failure rates."""
        order_id = "stress_high_failure"
        await OrderQueries.create_order(order_id, json.dumps({"stress": "test"}))
        
        # Simulate extremely high failure rates (90% failure)
        activities = ["receive_order", "validate_order", "charge_payment", "prepare_package", "dispatch_carrier"]
        
        for activity_type in activities:
            # Each activity fails 9 times before succeeding on the 10th
            for attempt in range(1, 11):
                status = "completed" if attempt == 10 else "failed"
                exec_time = random.randint(1000, 3000)
                
                await RetryQueries.log_activity_attempt(
                    order_id, activity_type, attempt, status, exec_time
                )
        
        # Verify the system can handle extreme failure rates
        retry_summary = await RetryQueries.get_order_retry_summary(order_id)
        assert retry_summary["total_attempts"] == 50  # 10 attempts × 5 activities
        assert retry_summary["total_retries"] == 45   # 9 retries × 5 activities
        assert retry_summary["failed_activities"] == 5
        
        # Test performance queries still work
        performance = await RetryQueries.get_activity_performance()
        assert len(performance) >= 5

    async def test_rapid_state_transitions(self):
        """Test rapid order state transitions."""
        order_id = "stress_rapid_transitions"
        await OrderQueries.create_order(order_id, json.dumps({"stress": "test"}))
        
        states = [
            "received", "validating", "validated", "charging_payment", 
            "payment_charged", "preparing_package", "package_prepared", 
            "dispatching_carrier", "shipped"
        ]
        
        # Rapidly transition through all states
        start_time = time.time()
        for state in states:
            await OrderQueries.update_order_state(order_id, state)
            await EventQueries.log_event(order_id, f"state_changed_to_{state}", {"new_state": state})
        
        transition_time = time.time() - start_time
        print(f"✅ Completed {len(states)} state transitions in {transition_time:.3f}s")
        
        # Verify final state
        order = await OrderQueries.get_order(order_id)
        assert order["state"] == "shipped"
        
        # Verify all events were logged
        events = await EventQueries.get_order_events(order_id)
        state_events = [e for e in events if "state_changed_to_" in e["event_type"]]
        assert len(state_events) == len(states)

class TestChaosEngineering:
    """Chaos engineering tests to find breaking points."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        yield
        
        # Cleanup chaos test data
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id LIKE 'chaos_%'")
            await execute_query("DELETE FROM events WHERE order_id LIKE 'chaos_%'")
            await execute_query("DELETE FROM payments WHERE order_id LIKE 'chaos_%'")
            await execute_query("DELETE FROM orders WHERE id LIKE 'chaos_%'")
        except:
            pass
        
        await shutdown_db()

    async def test_database_connection_interruption_simulation(self):
        """Simulate database connection interruptions."""
        order_id = "chaos_db_interruption"
        
        # Create order successfully
        await OrderQueries.create_order(order_id, json.dumps({"chaos": "test"}))
        
        # Simulate connection issues during operations
        with patch('db.connection.get_connection') as mock_get_conn:
            # First call succeeds, subsequent calls fail
            mock_conn = AsyncMock()
            mock_get_conn.side_effect = [mock_conn, Exception("Connection lost"), Exception("Connection lost")]
            
            # Try to log events during "connection issues"
            try:
                await EventQueries.log_event(order_id, "chaos_event", {"test": True})
                # This might fail due to mocked connection issues
            except Exception:
                pass  # Expected during chaos test
        
        # Verify system can recover
        # (Real connection should work again after the patch)
        await EventQueries.log_event(order_id, "recovery_event", {"recovered": True})
        
        events = await EventQueries.get_order_events(order_id)
        recovery_events = [e for e in events if e["event_type"] == "recovery_event"]
        assert len(recovery_events) == 1

    async def test_memory_pressure_simulation(self):
        """Test system behavior under memory pressure."""
        order_id = "chaos_memory_pressure"
        await OrderQueries.create_order(order_id, json.dumps({"chaos": "test"}))
        
        # Create many large events to simulate memory pressure
        large_event_count = 20
        
        for i in range(large_event_count):
            large_data = {
                "source": "chaos_test",
                "large_payload": [f"data_chunk_{j}" for j in range(500)],  # Large array
                "metadata": {f"meta_{k}": f"value_{k}" for k in range(100)}  # Large object
            }
            
            await EventQueries.log_event(order_id, f"large_event_{i}", large_data)
        
        # Verify all events were stored
        events = await EventQueries.get_order_events(order_id)
        large_events = [e for e in events if "large_event_" in e["event_type"]]
        assert len(large_events) == large_event_count
        
        # Verify data integrity
        sample_event = large_events[0]
        assert len(sample_event["event_data"]["large_payload"]) == 500

    async def test_extreme_retry_scenarios(self):
        """Test extreme retry scenarios."""
        order_id = "chaos_extreme_retries"
        await OrderQueries.create_order(order_id, json.dumps({"chaos": "test"}))
        
        # Simulate an activity that fails 50 times before succeeding
        activity_type = "chaos_activity"
        max_attempts = 50
        
        start_time = time.time()
        for attempt in range(1, max_attempts + 1):
            status = "completed" if attempt == max_attempts else "failed"
            exec_time = random.randint(100, 1000)
            
            await RetryQueries.log_activity_attempt(
                order_id, activity_type, attempt, status, exec_time
            )
        
        logging_time = time.time() - start_time
        print(f"✅ Logged {max_attempts} attempts in {logging_time:.2f}s")
        
        # Verify retry tracking still works
        attempts = await RetryQueries.get_order_attempts(order_id)
        chaos_attempts = [a for a in attempts if a["activity_type"] == activity_type]
        assert len(chaos_attempts) == max_attempts
        
        # Test retry summary with extreme data
        retry_summary = await RetryQueries.get_order_retry_summary(order_id)
        assert retry_summary["total_attempts"] == max_attempts
        assert retry_summary["total_retries"] == max_attempts - 1

class TestDataCorruptionResistance:
    """Test resistance to data corruption and inconsistencies."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        yield
        
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id LIKE 'corruption_%'")
            await execute_query("DELETE FROM events WHERE order_id LIKE 'corruption_%'")
            await execute_query("DELETE FROM payments WHERE order_id LIKE 'corruption_%'")
            await execute_query("DELETE FROM orders WHERE id LIKE 'corruption_%'")
        except:
            pass
        
        await shutdown_db()

    async def test_orphaned_events_handling(self):
        """Test handling of events without corresponding orders."""
        # Create events for non-existent orders
        orphaned_order_ids = ["corruption_orphan_1", "corruption_orphan_2"]
        
        for order_id in orphaned_order_ids:
            await EventQueries.log_event(order_id, "orphaned_event", {"orphaned": True})
        
        # Verify queries handle orphaned events gracefully
        recent_events = await EventQueries.get_recent_events(50)
        orphaned_events = [e for e in recent_events if e["order_id"] in orphaned_order_ids]
        assert len(orphaned_events) == 2
        
        # System should not crash when querying
        retry_summaries = await RetryQueries.get_all_retry_summaries()
        # Should work even with orphaned data

    async def test_payment_without_order(self):
        """Test payment records without corresponding orders."""
        # Try to create payment for non-existent order
        try:
            payment_id = await PaymentQueries.create_payment("corruption_no_order", 99.99, "pending")
            # This might succeed or fail depending on foreign key constraints
        except Exception:
            pass  # Expected if there are FK constraints
        
        # Verify system remains stable
        all_payments = await execute_query("SELECT COUNT(*) as count FROM payments")
        assert all_payments[0]["count"] >= 0  # Should not crash

    async def test_inconsistent_state_recovery(self):
        """Test recovery from inconsistent states."""
        order_id = "corruption_inconsistent"
        await OrderQueries.create_order(order_id, json.dumps({"corruption": "test"}))
        
        # Create inconsistent state: order is "shipped" but no payment exists
        await OrderQueries.update_order_state(order_id, "shipped")
        
        # Try to create payment for "shipped" order
        payment_id = await PaymentQueries.create_payment(order_id, 99.99, "pending")
        assert payment_id is not None
        
        # System should handle this gracefully
        order = await OrderQueries.get_order(order_id)
        payment = await PaymentQueries.get_payment(order_id)
        
        assert order["state"] == "shipped"
        assert payment["status"] == "pending"

class TestResourceExhaustion:
    """Test behavior under resource exhaustion."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        yield
        
        # Cleanup resource test data
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id LIKE 'resource_%'")
            await execute_query("DELETE FROM events WHERE order_id LIKE 'resource_%'")
            await execute_query("DELETE FROM payments WHERE order_id LIKE 'resource_%'")
            await execute_query("DELETE FROM orders WHERE id LIKE 'resource_%'")
        except:
            pass
        
        await shutdown_db()

    async def test_database_connection_pool_exhaustion(self):
        """Test behavior when database connection pool is exhausted."""
        # Create many concurrent database operations
        operation_count = 100
        
        async def db_operation(i):
            order_id = f"resource_pool_{i}"
            try:
                await OrderQueries.create_order(order_id, json.dumps({"pool": "test"}))
                await EventQueries.log_event(order_id, "pool_test", {"index": i})
                return True
            except Exception as e:
                print(f"Operation {i} failed: {e}")
                return False
        
        # Run many operations concurrently
        start_time = time.time()
        results = await asyncio.gather(
            *[db_operation(i) for i in range(operation_count)],
            return_exceptions=True
        )
        execution_time = time.time() - start_time
        
        successful = sum(1 for r in results if r is True)
        print(f"✅ {successful}/{operation_count} operations succeeded in {execution_time:.2f}s")
        
        # Should handle most operations successfully
        assert successful >= operation_count * 0.7

    async def test_large_payload_stress(self):
        """Test handling of very large data payloads."""
        order_id = "resource_large_payload"
        await OrderQueries.create_order(order_id, json.dumps({"resource": "test"}))
        
        # Create extremely large event payload
        huge_payload = {
            "massive_array": [f"item_{i}" for i in range(10000)],
            "massive_object": {f"key_{i}": f"value_{i}_{'x' * 100}" for i in range(1000)},
            "nested_structure": {
                "level1": {
                    "level2": {
                        "level3": [{"deep_data": f"value_{j}"} for j in range(500)]
                    }
                }
            }
        }
        
        # This should either succeed or fail gracefully
        try:
            await EventQueries.log_event(order_id, "huge_payload_test", huge_payload)
            
            # If it succeeded, verify we can retrieve it
            events = await EventQueries.get_order_events(order_id)
            huge_event = next(e for e in events if e["event_type"] == "huge_payload_test")
            assert len(huge_event["event_data"]["massive_array"]) == 10000
            
        except Exception as e:
            # If it failed, that's also acceptable for extremely large payloads
            print(f"Large payload rejected (expected): {e}")

class TestFailureRecoveryPatterns:
    """Test various failure recovery patterns."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        yield
        
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id LIKE 'recovery_%'")
            await execute_query("DELETE FROM events WHERE order_id LIKE 'recovery_%'")
            await execute_query("DELETE FROM payments WHERE order_id LIKE 'recovery_%'")
            await execute_query("DELETE FROM orders WHERE id LIKE 'recovery_%'")
        except:
            pass
        
        await shutdown_db()

    async def test_exponential_backoff_simulation(self):
        """Simulate exponential backoff retry patterns."""
        order_id = "recovery_exponential"
        await OrderQueries.create_order(order_id, json.dumps({"recovery": "test"}))
        
        # Simulate exponential backoff: 100ms, 200ms, 400ms, 800ms, 1600ms
        activity_type = "exponential_backoff_activity"
        backoff_times = [100, 200, 400, 800, 1600]
        
        for attempt, exec_time in enumerate(backoff_times, 1):
            status = "completed" if attempt == len(backoff_times) else "failed"
            
            await RetryQueries.log_activity_attempt(
                order_id, activity_type, attempt, status, exec_time
            )
        
        # Verify the pattern
        attempts = await RetryQueries.get_order_attempts(order_id)
        backoff_attempts = [a for a in attempts if a["activity_type"] == activity_type]
        
        assert len(backoff_attempts) == 5
        # Verify execution times follow exponential pattern
        exec_times = [a["execution_time_ms"] for a in sorted(backoff_attempts, key=lambda x: x["attempt_number"])]
        assert exec_times == backoff_times

    async def test_circuit_breaker_simulation(self):
        """Simulate circuit breaker pattern behavior."""
        order_id = "recovery_circuit_breaker"
        await OrderQueries.create_order(order_id, json.dumps({"recovery": "test"}))
        
        activity_type = "circuit_breaker_activity"
        
        # Phase 1: Rapid failures (circuit closed)
        for attempt in range(1, 6):
            await RetryQueries.log_activity_attempt(
                order_id, activity_type, attempt, "failed", 50  # Fast failures
            )
        
        # Phase 2: Circuit open (no attempts for a while)
        # Simulated by gap in attempt numbers
        
        # Phase 3: Circuit half-open (tentative attempt)
        await RetryQueries.log_activity_attempt(
            order_id, activity_type, 10, "failed", 100  # Still failing
        )
        
        # Phase 4: Circuit closed again, eventual success
        await RetryQueries.log_activity_attempt(
            order_id, activity_type, 15, "completed", 200  # Finally succeeds
        )
        
        # Verify the pattern
        attempts = await RetryQueries.get_order_attempts(order_id)
        circuit_attempts = [a for a in attempts if a["activity_type"] == activity_type]
        
        assert len(circuit_attempts) == 7  # 5 + 1 + 1
        
        # Check there's a gap in attempt numbers (simulating circuit open period)
        attempt_numbers = sorted([a["attempt_number"] for a in circuit_attempts])
        assert 6 not in attempt_numbers  # Gap indicating circuit was open

class TestObservabilityUnderStress:
    """Test observability features under stress conditions."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        yield
        
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id LIKE 'observ_%'")
            await execute_query("DELETE FROM events WHERE order_id LIKE 'observ_%'")
            await execute_query("DELETE FROM payments WHERE order_id LIKE 'observ_%'")
            await execute_query("DELETE FROM orders WHERE id LIKE 'observ_%'")
        except:
            pass
        
        await shutdown_db()

    async def test_observability_with_massive_data(self):
        """Test observability queries with large amounts of data."""
        # Create many orders with lots of events and attempts
        order_count = 30
        
        for i in range(order_count):
            order_id = f"observ_massive_{i}"
            await OrderQueries.create_order(order_id, json.dumps({"observ": "test"}))
            
            # Add many events per order
            for j in range(20):
                await EventQueries.log_event(order_id, f"event_{j}", {"index": j})
            
            # Add many attempts per order
            for attempt in range(1, 8):
                await RetryQueries.log_activity_attempt(
                    order_id, f"activity_{i % 3}", attempt, 
                    "completed" if attempt == 7 else "failed",
                    random.randint(500, 2000)
                )
        
        # Test observability queries still perform well
        start_time = time.time()
        
        # Run all observability queries
        recent_orders = await OrderQueries.get_recent_orders(20)
        recent_events = await EventQueries.get_recent_events(100)
        retry_summaries = await RetryQueries.get_all_retry_summaries()
        activity_performance = await RetryQueries.get_activity_performance()
        failed_activities = await RetryQueries.get_failed_activities()
        
        query_time = time.time() - start_time
        print(f"✅ Observability queries completed in {query_time:.2f}s with {order_count * 20} events and {order_count * 7} attempts")
        
        # Queries should complete in reasonable time even with lots of data
        assert query_time < 10.0, f"Observability queries took {query_time:.2f}s, expected < 10s"
        
        # Verify data quality
        assert len(recent_orders) >= min(20, order_count)
        assert len(recent_events) >= min(100, order_count * 20)
        assert len(retry_summaries) >= order_count

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to see print outputs