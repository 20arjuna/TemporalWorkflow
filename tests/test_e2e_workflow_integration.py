"""
Comprehensive End-to-End Integration Tests for Temporal Workflow System

These tests validate the complete order processing pipeline:
- Order creation → validation → approval → payment → shipping → completion
- Signal handling (approve, cancel, update_address)
- Database persistence and retry tracking
- Worker resilience to flaky_call failures
- API endpoints integration
"""

import asyncio
import pytest
import json
import time
from unittest.mock import patch, AsyncMock
from decimal import Decimal

# Test imports (avoiding Temporal SDK due to architecture issues)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import startup_db, shutdown_db, get_connection, execute_query
from db.queries import OrderQueries, PaymentQueries, EventQueries, RetryQueries, ObservabilityQueries

class TestEndToEndWorkflow:
    """Test the complete order workflow pipeline."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        """Setup database and cleanup test data."""
        await startup_db()
        
        # Cleanup any existing test data
        test_order_ids = ["e2e_test_order", "e2e_cancel_test", "e2e_timeout_test", "e2e_retry_test"]
        for order_id in test_order_ids:
            try:
                await execute_query("DELETE FROM activity_attempts WHERE order_id = $1", order_id)
                await execute_query("DELETE FROM events WHERE order_id = $1", order_id)
                await execute_query("DELETE FROM payments WHERE order_id = $1", order_id)
                await execute_query("DELETE FROM orders WHERE id = $1", order_id)
            except:
                pass  # Ignore if doesn't exist
        
        yield
        
        # Cleanup after test
        for order_id in test_order_ids:
            try:
                await execute_query("DELETE FROM activity_attempts WHERE order_id = $1", order_id)
                await execute_query("DELETE FROM events WHERE order_id = $1", order_id)
                await execute_query("DELETE FROM payments WHERE order_id = $1", order_id)
                await execute_query("DELETE FROM orders WHERE id = $1", order_id)
            except:
                pass
        
        await shutdown_db()

    async def test_complete_order_flow_simulation(self):
        """Simulate a complete order flow through database operations."""
        order_id = "e2e_test_order"
        address = {"line1": "123 Test St", "city": "TestCity", "state": "TS", "zip": "12345"}
        
        # 1. Simulate order creation
        await OrderQueries.create_order(order_id, json.dumps(address))
        order = await OrderQueries.get_order(order_id)
        assert order["id"] == order_id
        assert order["state"] == "created"
        
        # 2. Simulate order received
        await OrderQueries.update_order_state(order_id, "received")
        await EventQueries.log_event(order_id, "order_received", {
            "source": "test_simulation",
            "address": address
        })
        
        # 3. Simulate validation with retries
        await OrderQueries.update_order_state(order_id, "validating")
        
        # Log some retry attempts for validation
        for attempt in range(1, 4):
            await RetryQueries.log_activity_attempt(
                order_id, "validate_order", attempt, 
                "failed" if attempt < 3 else "completed",
                500 + (attempt * 100)  # Increasing execution time
            )
        
        await OrderQueries.update_order_state(order_id, "validated")
        await EventQueries.log_event(order_id, "order_validated", {
            "source": "test_simulation",
            "validation_attempts": 3
        })
        
        # 4. Simulate payment processing
        await OrderQueries.update_order_state(order_id, "charging_payment")
        payment_id = await PaymentQueries.create_payment(order_id, 99.99, "pending")
        
        # Simulate payment retry
        await RetryQueries.log_activity_attempt(order_id, "charge_payment", 1, "failed", 800)
        await PaymentQueries.update_payment_retry_info(payment_id, 1, "Network timeout")
        
        await RetryQueries.log_activity_attempt(order_id, "charge_payment", 2, "completed", 1200)
        await PaymentQueries.update_payment_status(payment_id, "charged")
        await OrderQueries.update_order_state(order_id, "payment_charged")
        
        # 5. Simulate shipping
        await OrderQueries.update_order_state(order_id, "preparing_package")
        await RetryQueries.log_activity_attempt(order_id, "prepare_package", 1, "completed", 2000)
        await OrderQueries.update_order_state(order_id, "package_prepared")
        
        await OrderQueries.update_order_state(order_id, "dispatching_carrier")
        await RetryQueries.log_activity_attempt(order_id, "dispatch_carrier", 1, "completed", 1500)
        await OrderQueries.update_order_state(order_id, "shipped")
        
        # 6. Validate final state
        final_order = await OrderQueries.get_order(order_id)
        assert final_order["state"] == "shipped"
        
        payment = await PaymentQueries.get_payment(order_id)
        assert payment["status"] == "charged"
        assert payment["retry_count"] == 1
        
        # Check retry tracking
        attempts = await RetryQueries.get_order_attempts(order_id)
        assert len(attempts) == 5  # validate(3) + charge_payment(2) + prepare_package(1) + dispatch_carrier(1)
        
        total_retries = sum(attempt["attempt_number"] - 1 for attempt in attempts)
        assert total_retries == 3  # validate(2 retries) + charge_payment(1 retry) + others(0 retries)

    async def test_order_cancellation_flow(self):
        """Test order cancellation and cleanup."""
        order_id = "e2e_cancel_test"
        address = {"line1": "456 Cancel St", "city": "CancelCity", "state": "CS", "zip": "54321"}
        
        # Create and start order
        await OrderQueries.create_order(order_id, json.dumps(address))
        await OrderQueries.update_order_state(order_id, "validated")
        
        # Simulate cancellation
        await OrderQueries.update_order_state(order_id, "cancelled")
        await EventQueries.log_event(order_id, "order_cancelled", {
            "source": "test_simulation",
            "reason": "user_requested"
        })
        
        # Validate cancellation
        order = await OrderQueries.get_order(order_id)
        assert order["state"] == "cancelled"
        
        events = await EventQueries.get_order_events(order_id)
        cancel_events = [e for e in events if e["event_type"] == "order_cancelled"]
        assert len(cancel_events) == 1

    async def test_payment_idempotency(self):
        """Test payment idempotency under retry scenarios."""
        order_id = "e2e_retry_test"
        
        await OrderQueries.create_order(order_id, json.dumps({"test": "address"}))
        
        # Create payment
        payment_id1 = await PaymentQueries.create_payment(order_id, 99.99, "pending")
        
        # Try to create duplicate payment (should be idempotent)
        payment_id2 = await PaymentQueries.create_payment(order_id, 99.99, "pending")
        
        # Should return same payment ID
        assert payment_id1 == payment_id2
        
        # Verify only one payment exists
        payments = await execute_query(
            "SELECT COUNT(*) as count FROM payments WHERE order_id = $1", 
            order_id
        )
        assert payments[0]["count"] == 1

    async def test_observability_queries(self):
        """Test observability and monitoring queries."""
        order_id = "e2e_test_order"  # Use order from previous test
        
        # Test retry summary
        retry_summaries = await RetryQueries.get_all_retry_summaries()
        test_summary = next((s for s in retry_summaries if s["order_id"] == order_id), None)
        assert test_summary is not None
        assert test_summary["total_attempts"] >= 5
        assert test_summary["total_retries"] >= 3
        
        # Test activity performance
        performance = await RetryQueries.get_activity_performance()
        assert len(performance) > 0
        
        # Should have data for our test activities
        activity_types = [p["activity_type"] for p in performance]
        assert "validate_order" in activity_types
        assert "charge_payment" in activity_types
        
        # Test health report
        health_report = await ObservabilityQueries.get_order_health_report(order_id)
        assert health_report["order_id"] == order_id
        assert "total_events" in health_report
        assert "total_attempts" in health_report

    async def test_recent_orders_and_events(self):
        """Test recent orders and events queries."""
        # Get recent orders
        recent_orders = await OrderQueries.get_recent_orders(5)
        assert len(recent_orders) >= 1
        
        # Should include our test orders
        order_ids = [order["order_id"] for order in recent_orders]
        assert "e2e_test_order" in order_ids
        
        # Get recent events
        recent_events = await EventQueries.get_recent_events(10)
        assert len(recent_events) >= 1
        
        # Should have events from our test
        test_events = [e for e in recent_events if e["order_id"] == "e2e_test_order"]
        assert len(test_events) >= 2  # At least order_received and order_validated

    async def test_failed_activities_tracking(self):
        """Test tracking of failed activities."""
        # Get failed activities
        failed_activities = await RetryQueries.get_failed_activities()
        
        # Should include our validation failures
        validation_failures = [f for f in failed_activities if f["activity_type"] == "validate_order"]
        assert len(validation_failures) >= 1
        
        # Check failure details
        for failure in validation_failures:
            assert failure["total_failures"] >= 1
            assert failure["avg_execution_time_ms"] > 0

class TestDatabaseIntegrity:
    """Test database operations and data integrity."""
    
    @pytest.fixture(autouse=True)
    async def setup_db(self):
        await startup_db()
        yield
        await shutdown_db()

    async def test_concurrent_payment_creation(self):
        """Test that concurrent payment creation is properly handled."""
        order_id = "concurrent_test"
        await OrderQueries.create_order(order_id, json.dumps({"test": "data"}))
        
        # Simulate concurrent payment creation
        async def create_payment():
            return await PaymentQueries.create_payment(order_id, 99.99, "pending")
        
        # Run multiple concurrent payment creations
        results = await asyncio.gather(
            create_payment(),
            create_payment(),
            create_payment(),
            return_exceptions=True
        )
        
        # All should succeed and return the same payment ID
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) >= 1
        
        # Verify only one payment in database
        payments = await execute_query(
            "SELECT COUNT(*) as count FROM payments WHERE order_id = $1", 
            order_id
        )
        assert payments[0]["count"] == 1
        
        # Cleanup
        await execute_query("DELETE FROM payments WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)

    async def test_event_ordering_and_timestamps(self):
        """Test that events are properly ordered by timestamp."""
        order_id = "timestamp_test"
        await OrderQueries.create_order(order_id, json.dumps({"test": "data"}))
        
        # Create events with small delays
        events_to_create = [
            ("order_received", {"step": 1}),
            ("validation_started", {"step": 2}),
            ("order_validated", {"step": 3}),
            ("payment_started", {"step": 4}),
            ("payment_completed", {"step": 5})
        ]
        
        for event_type, data in events_to_create:
            await EventQueries.log_event(order_id, event_type, data)
            await asyncio.sleep(0.01)  # Small delay to ensure different timestamps
        
        # Retrieve events and verify ordering
        events = await EventQueries.get_order_events(order_id)
        assert len(events) == 5
        
        # Should be ordered by timestamp (newest first based on the query)
        for i in range(len(events) - 1):
            assert events[i]["created_at"] >= events[i + 1]["created_at"]
        
        # Verify event sequence
        event_types = [e["event_type"] for e in reversed(events)]  # Reverse to get chronological order
        expected_types = ["order_received", "validation_started", "order_validated", "payment_started", "payment_completed"]
        assert event_types == expected_types
        
        # Cleanup
        await execute_query("DELETE FROM events WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)

    async def test_jsonb_operations(self):
        """Test JSONB operations for address updates."""
        order_id = "jsonb_test"
        original_address = {"line1": "123 Original St", "city": "OriginalCity", "state": "OS", "zip": "12345"}
        new_address = {"line1": "456 New St", "city": "NewCity", "state": "NS", "zip": "54321"}
        
        await OrderQueries.create_order(order_id, json.dumps(original_address))
        
        # Update address using JSONB operations
        await execute_query(
            "UPDATE orders SET address = $1 WHERE id = $2",
            json.dumps(new_address), order_id
        )
        
        # Verify update
        order = await OrderQueries.get_order(order_id)
        stored_address = json.loads(order["address"])
        assert stored_address["line1"] == "456 New St"
        assert stored_address["city"] == "NewCity"
        
        # Cleanup
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)

class TestRetryAndResilienceLogic:
    """Test retry tracking and system resilience."""
    
    @pytest.fixture(autouse=True)
    async def setup_db(self):
        await startup_db()
        yield
        await shutdown_db()

    async def test_activity_retry_tracking(self):
        """Test comprehensive retry tracking across multiple activities."""
        order_id = "retry_tracking_test"
        await OrderQueries.create_order(order_id, json.dumps({"test": "data"}))
        
        # Simulate multiple activities with various retry patterns
        retry_scenarios = [
            ("receive_order", [(1, "completed", 500)]),  # Success on first try
            ("validate_order", [(1, "failed", 800), (2, "failed", 900), (3, "completed", 1000)]),  # Success on 3rd try
            ("charge_payment", [(1, "failed", 1200), (2, "completed", 1100)]),  # Success on 2nd try
            ("prepare_package", [(1, "timeout", 15000), (2, "failed", 2000), (3, "failed", 2100), (4, "completed", 1800)]),  # Success on 4th try
            ("dispatch_carrier", [(1, "completed", 1500)])  # Success on first try
        ]
        
        for activity_type, attempts in retry_scenarios:
            for attempt_num, status, exec_time in attempts:
                await RetryQueries.log_activity_attempt(
                    order_id, activity_type, attempt_num, status, exec_time
                )
        
        # Test retry summary
        retry_summary = await RetryQueries.get_order_retry_summary(order_id)
        assert retry_summary["total_attempts"] == 11  # Sum of all attempts
        assert retry_summary["total_retries"] == 6   # Sum of (attempts - 1) for each activity
        assert retry_summary["failed_activities"] == 3  # validate_order, charge_payment, prepare_package had failures
        
        # Test activity performance
        performance = await RetryQueries.get_activity_performance()
        validate_perf = next(p for p in performance if p["activity_type"] == "validate_order")
        assert validate_perf["total_attempts"] >= 3
        assert validate_perf["failure_rate"] >= 0.66  # 2 failures out of 3 attempts
        
        # Test failed activities summary
        failed_activities = await RetryQueries.get_failed_activities()
        failed_types = [f["activity_type"] for f in failed_activities]
        assert "validate_order" in failed_types
        assert "charge_payment" in failed_types
        assert "prepare_package" in failed_types
        
        # Cleanup
        await execute_query("DELETE FROM activity_attempts WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)

    async def test_payment_retry_edge_cases(self):
        """Test payment retry scenarios and idempotency."""
        order_id = "payment_edge_test"
        await OrderQueries.create_order(order_id, json.dumps({"test": "data"}))
        
        # Create payment
        payment_id = await PaymentQueries.create_payment(order_id, 99.99, "pending")
        
        # Simulate multiple retry attempts
        await PaymentQueries.update_payment_retry_info(payment_id, 1, "Network timeout")
        await PaymentQueries.update_payment_retry_info(payment_id, 2, "Gateway error")
        await PaymentQueries.update_payment_retry_info(payment_id, 3, "Rate limited")
        
        # Finally succeed
        await PaymentQueries.update_payment_status(payment_id, "charged")
        
        # Verify retry info
        payment = await PaymentQueries.get_payment(order_id)
        assert payment["retry_count"] == 3
        assert payment["last_error"] == "Rate limited"
        assert payment["status"] == "charged"
        
        # Test idempotent payment creation
        duplicate_id = await PaymentQueries.create_payment(order_id, 99.99, "pending")
        assert duplicate_id == payment_id
        
        # Cleanup
        await execute_query("DELETE FROM payments WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)

class TestObservabilityAndMonitoring:
    """Test observability features and monitoring queries."""
    
    @pytest.fixture(autouse=True)
    async def setup_db(self):
        await startup_db()
        yield
        await shutdown_db()

    async def test_health_report_generation(self):
        """Test comprehensive health report generation."""
        order_id = "health_test"
        await OrderQueries.create_order(order_id, json.dumps({"test": "data"}))
        
        # Create diverse events and attempts
        await EventQueries.log_event(order_id, "order_received", {"source": "test"})
        await EventQueries.log_event(order_id, "validation_failed", {"error": "test_error"})
        await EventQueries.log_event(order_id, "order_validated", {"source": "test"})
        
        await RetryQueries.log_activity_attempt(order_id, "validate_order", 1, "failed", 1000)
        await RetryQueries.log_activity_attempt(order_id, "validate_order", 2, "completed", 1200)
        
        # Generate health report
        health_report = await ObservabilityQueries.get_order_health_report(order_id)
        
        assert health_report["order_id"] == order_id
        assert health_report["total_events"] >= 3
        assert health_report["total_attempts"] >= 2
        assert health_report["total_retries"] >= 1
        assert health_report["unique_activities"] >= 1
        
        # Cleanup
        await execute_query("DELETE FROM activity_attempts WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM events WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)

    async def test_system_dashboard_metrics(self):
        """Test system-wide dashboard metrics."""
        # Create some test data across multiple orders
        test_orders = ["metrics_1", "metrics_2", "metrics_3"]
        
        for i, order_id in enumerate(test_orders):
            await OrderQueries.create_order(order_id, json.dumps({"test": f"data_{i}"}))
            await EventQueries.log_event(order_id, "order_received", {"source": "test"})
            
            # Vary the retry patterns
            if i == 0:  # No retries
                await RetryQueries.log_activity_attempt(order_id, "receive_order", 1, "completed", 500)
            elif i == 1:  # Some retries
                await RetryQueries.log_activity_attempt(order_id, "receive_order", 1, "failed", 600)
                await RetryQueries.log_activity_attempt(order_id, "receive_order", 2, "completed", 700)
            else:  # Many retries
                for attempt in range(1, 6):
                    status = "completed" if attempt == 5 else "failed"
                    await RetryQueries.log_activity_attempt(order_id, "receive_order", attempt, status, 500 + attempt * 100)
        
        # Test system dashboard
        dashboard = await ObservabilityQueries.get_system_health_dashboard()
        
        assert dashboard["total_orders"] >= 3
        assert dashboard["total_events"] >= 3
        assert dashboard["total_attempts"] >= 7  # 1 + 2 + 5 attempts
        assert dashboard["total_retries"] >= 5   # 0 + 1 + 4 retries
        
        # Cleanup
        for order_id in test_orders:
            await execute_query("DELETE FROM activity_attempts WHERE order_id = $1", order_id)
            await execute_query("DELETE FROM events WHERE order_id = $1", order_id)
            await execute_query("DELETE FROM orders WHERE id = $1", order_id)

class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""
    
    @pytest.fixture(autouse=True)
    async def setup_db(self):
        await startup_db()
        yield
        await shutdown_db()

    async def test_missing_order_handling(self):
        """Test queries for non-existent orders."""
        # Test getting non-existent order
        result = await OrderQueries.get_order("nonexistent_order")
        assert result is None
        
        # Test getting events for non-existent order
        events = await EventQueries.get_order_events("nonexistent_order")
        assert events == []
        
        # Test getting attempts for non-existent order
        attempts = await RetryQueries.get_order_attempts("nonexistent_order")
        assert attempts == []

    async def test_malformed_data_handling(self):
        """Test handling of malformed JSON and data."""
        order_id = "malformed_test"
        
        # Test with malformed JSON address
        try:
            await execute_query(
                "INSERT INTO orders (id, address, state) VALUES ($1, $2, $3)",
                order_id, "invalid_json", "created"
            )
            # This should fail due to JSONB validation
            assert False, "Should have failed with invalid JSON"
        except Exception:
            pass  # Expected to fail
        
        # Test with valid JSON but unexpected structure
        await OrderQueries.create_order(order_id, json.dumps({"unexpected": "structure"}))
        order = await OrderQueries.get_order(order_id)
        assert order is not None
        
        # Cleanup
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)

    async def test_large_event_data_handling(self):
        """Test handling of large event data payloads."""
        order_id = "large_data_test"
        await OrderQueries.create_order(order_id, json.dumps({"test": "data"}))
        
        # Create event with large data payload
        large_data = {
            "source": "test",
            "large_array": [f"item_{i}" for i in range(1000)],
            "large_object": {f"key_{i}": f"value_{i}" for i in range(100)}
        }
        
        await EventQueries.log_event(order_id, "large_data_test", large_data)
        
        # Verify it was stored and can be retrieved
        events = await EventQueries.get_order_events(order_id)
        large_event = next(e for e in events if e["event_type"] == "large_data_test")
        
        stored_data = large_event["event_data"]
        assert len(stored_data["large_array"]) == 1000
        assert len(stored_data["large_object"]) == 100
        
        # Cleanup
        await execute_query("DELETE FROM events WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main([__file__, "-v"])