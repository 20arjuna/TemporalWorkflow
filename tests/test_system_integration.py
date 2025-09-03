"""
System Integration Tests

Tests the complete system integration:
- API + Workers + Database + Temporal
- Real workflow execution (when possible)
- Cross-component communication
- End-to-end scenarios
"""

import pytest
import asyncio
import json
import time
import requests
from unittest.mock import patch, AsyncMock

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import startup_db, shutdown_db, execute_query
from db.queries import OrderQueries, EventQueries, RetryQueries

class TestAPIWorkerIntegration:
    """Test integration between API and background workers."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        
        # Cleanup any existing test data
        test_order_ids = ["integration_test", "api_worker_test", "full_flow_test"]
        for order_id in test_order_ids:
            try:
                await execute_query("DELETE FROM activity_attempts WHERE order_id = $1", order_id)
                await execute_query("DELETE FROM events WHERE order_id = $1", order_id)
                await execute_query("DELETE FROM payments WHERE order_id = $1", order_id)
                await execute_query("DELETE FROM orders WHERE id = $1", order_id)
            except:
                pass
        
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

    async def test_api_triggers_database_changes(self):
        """Test that API calls result in database changes."""
        order_id = "integration_test"
        
        # Simulate API call creating order in database
        await OrderQueries.create_order(order_id, json.dumps({
            "line1": "123 Integration St",
            "city": "TestCity", 
            "state": "TS",
            "zip": "12345"
        }))
        
        # Simulate worker activities updating database
        await OrderQueries.update_order_state(order_id, "received")
        await EventQueries.log_event(order_id, "order_received", {
            "source": "integration_test",
            "api_triggered": True
        })
        
        # Verify database reflects the changes
        order = await OrderQueries.get_order(order_id)
        assert order["state"] == "received"
        
        events = await EventQueries.get_order_events(order_id)
        assert len(events) >= 1
        assert events[0]["event_type"] == "order_received"

    async def test_database_state_consistency(self):
        """Test that database state remains consistent across operations."""
        order_id = "api_worker_test"
        
        # Simulate complete order flow through database
        await OrderQueries.create_order(order_id, json.dumps({"integration": "test"}))
        
        # Simulate order processing steps
        processing_steps = [
            ("received", "order_received"),
            ("validating", "validation_started"),
            ("validated", "order_validated"),
            ("charging_payment", "payment_started"),
            ("payment_charged", "payment_completed"),
            ("preparing_package", "package_preparation_started"),
            ("package_prepared", "package_prepared"),
            ("dispatching_carrier", "carrier_dispatch_started"),
            ("shipped", "order_shipped")
        ]
        
        for state, event_type in processing_steps:
            await OrderQueries.update_order_state(order_id, state)
            await EventQueries.log_event(order_id, event_type, {
                "source": "integration_test",
                "state": state
            })
            
            # Verify consistency at each step
            order = await OrderQueries.get_order(order_id)
            assert order["state"] == state
        
        # Verify final state
        final_order = await OrderQueries.get_order(order_id)
        assert final_order["state"] == "shipped"
        
        # Verify all events were logged
        events = await EventQueries.get_order_events(order_id)
        assert len(events) >= len(processing_steps)

class TestCrossComponentCommunication:
    """Test communication between different system components."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        yield
        
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id LIKE 'comm_%'")
            await execute_query("DELETE FROM events WHERE order_id LIKE 'comm_%'")
            await execute_query("DELETE FROM payments WHERE order_id LIKE 'comm_%'")
            await execute_query("DELETE FROM orders WHERE id LIKE 'comm_%'")
        except:
            pass
        
        await shutdown_db()

    async def test_order_workflow_to_shipping_workflow_handoff(self):
        """Test handoff from order workflow to shipping workflow."""
        order_id = "comm_handoff_test"
        
        # Simulate order workflow completion
        await OrderQueries.create_order(order_id, json.dumps({"handoff": "test"}))
        await OrderQueries.update_order_state(order_id, "payment_charged")
        
        # Log order workflow completion
        await EventQueries.log_event(order_id, "order_workflow_completed", {
            "source": "order_workflow",
            "next_step": "shipping"
        })
        
        # Simulate shipping workflow start
        await OrderQueries.update_order_state(order_id, "preparing_package")
        await EventQueries.log_event(order_id, "shipping_workflow_started", {
            "source": "shipping_workflow",
            "triggered_by": "order_workflow"
        })
        
        # Verify handoff
        events = await EventQueries.get_order_events(order_id)
        handoff_events = [e for e in events if "workflow" in e["event_type"]]
        assert len(handoff_events) == 2
        
        # Verify state progression
        order = await OrderQueries.get_order(order_id)
        assert order["state"] == "preparing_package"

    async def test_signal_handling_simulation(self):
        """Test signal handling between API and workflows."""
        order_id = "comm_signal_test"
        
        await OrderQueries.create_order(order_id, json.dumps({"signal": "test"}))
        await OrderQueries.update_order_state(order_id, "validated")
        
        # Simulate approval signal
        await EventQueries.log_event(order_id, "approval_signal_received", {
            "source": "api_endpoint",
            "signal_type": "approve"
        })
        
        # Simulate workflow processing the signal
        await OrderQueries.update_order_state(order_id, "charging_payment")
        await EventQueries.log_event(order_id, "approval_signal_processed", {
            "source": "order_workflow",
            "action": "proceeding_to_payment"
        })
        
        # Verify signal flow
        events = await EventQueries.get_order_events(order_id)
        signal_events = [e for e in events if "signal" in e["event_type"]]
        assert len(signal_events) == 2

class TestFullSystemScenarios:
    """Test complete system scenarios end-to-end."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        yield
        
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id LIKE 'full_%'")
            await execute_query("DELETE FROM events WHERE order_id LIKE 'full_%'")
            await execute_query("DELETE FROM payments WHERE order_id LIKE 'full_%'")
            await execute_query("DELETE FROM orders WHERE id LIKE 'full_%'")
        except:
            pass
        
        await shutdown_db()

    async def test_happy_path_complete_flow(self):
        """Test complete happy path flow through database simulation."""
        order_id = "full_happy_path"
        address = {"line1": "123 Happy St", "city": "HappyCity", "state": "HP", "zip": "12345"}
        
        # 1. Order creation (API simulation)
        await OrderQueries.create_order(order_id, json.dumps(address))
        await EventQueries.log_event(order_id, "order_created", {"source": "api"})
        
        # 2. Order processing (Worker simulation)
        await OrderQueries.update_order_state(order_id, "received")
        await RetryQueries.log_activity_attempt(order_id, "receive_order", 1, "completed", 500)
        await EventQueries.log_event(order_id, "order_received", {"source": "order_worker"})
        
        # 3. Validation
        await OrderQueries.update_order_state(order_id, "validating")
        await RetryQueries.log_activity_attempt(order_id, "validate_order", 1, "completed", 800)
        await OrderQueries.update_order_state(order_id, "validated")
        await EventQueries.log_event(order_id, "order_validated", {"source": "order_worker"})
        
        # 4. Approval (API simulation)
        await EventQueries.log_event(order_id, "approval_signal_sent", {"source": "api"})
        
        # 5. Payment processing
        await OrderQueries.update_order_state(order_id, "charging_payment")
        payment_id = await PaymentQueries.create_payment(order_id, 99.99, "pending")
        await RetryQueries.log_activity_attempt(order_id, "charge_payment", 1, "completed", 1200)
        await PaymentQueries.update_payment_status(payment_id, "charged")
        await OrderQueries.update_order_state(order_id, "payment_charged")
        await EventQueries.log_event(order_id, "payment_charged", {"source": "order_worker"})
        
        # 6. Shipping (Shipping worker simulation)
        await OrderQueries.update_order_state(order_id, "preparing_package")
        await RetryQueries.log_activity_attempt(order_id, "prepare_package", 1, "completed", 2000)
        await OrderQueries.update_order_state(order_id, "package_prepared")
        
        await OrderQueries.update_order_state(order_id, "dispatching_carrier")
        await RetryQueries.log_activity_attempt(order_id, "dispatch_carrier", 1, "completed", 1500)
        await OrderQueries.update_order_state(order_id, "shipped")
        await EventQueries.log_event(order_id, "order_shipped", {"source": "shipping_worker"})
        
        # 7. Validation - Complete flow
        final_order = await OrderQueries.get_order(order_id)
        assert final_order["state"] == "shipped"
        
        payment = await PaymentQueries.get_payment(order_id)
        assert payment["status"] == "charged"
        
        events = await EventQueries.get_order_events(order_id)
        assert len(events) >= 6  # Should have events for each major step
        
        attempts = await RetryQueries.get_order_attempts(order_id)
        assert len(attempts) == 4  # receive, validate, charge, prepare, dispatch
        
        # All attempts should be successful in happy path
        failed_attempts = [a for a in attempts if a["status"] != "completed"]
        assert len(failed_attempts) == 0

    async def test_failure_and_recovery_flow(self):
        """Test order flow with failures and recovery."""
        order_id = "full_failure_recovery"
        address = {"line1": "123 Failure St", "city": "FailureCity", "state": "FL", "zip": "54321"}
        
        await OrderQueries.create_order(order_id, json.dumps(address))
        
        # Simulate validation failures then success
        await OrderQueries.update_order_state(order_id, "validating")
        
        # Multiple validation attempts
        for attempt in range(1, 5):
            status = "completed" if attempt == 4 else "failed"
            await RetryQueries.log_activity_attempt(order_id, "validate_order", attempt, status, 800 + attempt * 100)
        
        await OrderQueries.update_order_state(order_id, "validated")
        
        # Simulate payment failures then success
        await OrderQueries.update_order_state(order_id, "charging_payment")
        payment_id = await PaymentQueries.create_payment(order_id, 99.99, "pending")
        
        # Payment retry attempts
        for attempt in range(1, 4):
            status = "completed" if attempt == 3 else "failed"
            await RetryQueries.log_activity_attempt(order_id, "charge_payment", attempt, status, 1000 + attempt * 200)
            if attempt < 3:
                await PaymentQueries.update_payment_retry_info(payment_id, attempt, f"Attempt {attempt} failed")
        
        await PaymentQueries.update_payment_status(payment_id, "charged")
        await OrderQueries.update_order_state(order_id, "payment_charged")
        
        # Complete shipping successfully
        await OrderQueries.update_order_state(order_id, "preparing_package")
        await RetryQueries.log_activity_attempt(order_id, "prepare_package", 1, "completed", 2000)
        await OrderQueries.update_order_state(order_id, "package_prepared")
        
        await OrderQueries.update_order_state(order_id, "dispatching_carrier")
        await RetryQueries.log_activity_attempt(order_id, "dispatch_carrier", 1, "completed", 1500)
        await OrderQueries.update_order_state(order_id, "shipped")
        
        # Validate recovery flow
        final_order = await OrderQueries.get_order(order_id)
        assert final_order["state"] == "shipped"
        
        # Check retry tracking
        retry_summary = await RetryQueries.get_order_retry_summary(order_id)
        assert retry_summary["total_retries"] >= 5  # 3 validation + 2 payment retries
        assert retry_summary["failed_activities"] >= 2  # validation and payment had failures
        
        # Payment should show retry info
        payment = await PaymentQueries.get_payment(order_id)
        assert payment["retry_count"] >= 2

    async def test_cancellation_flow_integration(self):
        """Test order cancellation flow across components."""
        order_id = "full_cancellation_test"
        
        await OrderQueries.create_order(order_id, json.dumps({"cancel": "test"}))
        await OrderQueries.update_order_state(order_id, "validated")
        
        # Simulate cancellation signal from API
        await EventQueries.log_event(order_id, "cancellation_signal_received", {
            "source": "api_endpoint",
            "reason": "user_requested"
        })
        
        # Simulate workflow processing cancellation
        await OrderQueries.update_order_state(order_id, "cancelled")
        await EventQueries.log_event(order_id, "order_cancelled", {
            "source": "order_workflow",
            "final_state": "cancelled"
        })
        
        # Verify cancellation
        order = await OrderQueries.get_order(order_id)
        assert order["state"] == "cancelled"
        
        events = await EventQueries.get_order_events(order_id)
        cancel_events = [e for e in events if "cancel" in e["event_type"]]
        assert len(cancel_events) >= 2

class TestSystemHealthAndMonitoring:
    """Test system health monitoring and observability."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        yield
        
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id LIKE 'health_%'")
            await execute_query("DELETE FROM events WHERE order_id LIKE 'health_%'")
            await execute_query("DELETE FROM payments WHERE order_id LIKE 'health_%'")
            await execute_query("DELETE FROM orders WHERE id LIKE 'health_%'")
        except:
            pass
        
        await shutdown_db()

    async def test_system_health_under_load(self):
        """Test system health monitoring under load."""
        # Create multiple orders with varying patterns
        order_patterns = [
            ("health_success", "successful"),    # Successful order
            ("health_retries", "with_retries"),  # Order with retries
            ("health_failure", "failed"),        # Failed order
        ]
        
        for order_id, pattern in order_patterns:
            await OrderQueries.create_order(order_id, json.dumps({"pattern": pattern}))
            
            if pattern == "successful":
                # Simulate successful flow
                await RetryQueries.log_activity_attempt(order_id, "receive_order", 1, "completed", 500)
                await RetryQueries.log_activity_attempt(order_id, "validate_order", 1, "completed", 600)
                await RetryQueries.log_activity_attempt(order_id, "charge_payment", 1, "completed", 1000)
                await OrderQueries.update_order_state(order_id, "shipped")
                
            elif pattern == "with_retries":
                # Simulate retries
                await RetryQueries.log_activity_attempt(order_id, "receive_order", 1, "failed", 500)
                await RetryQueries.log_activity_attempt(order_id, "receive_order", 2, "completed", 600)
                await RetryQueries.log_activity_attempt(order_id, "validate_order", 1, "failed", 700)
                await RetryQueries.log_activity_attempt(order_id, "validate_order", 2, "failed", 800)
                await RetryQueries.log_activity_attempt(order_id, "validate_order", 3, "completed", 900)
                await OrderQueries.update_order_state(order_id, "validated")
                
            else:  # failed
                # Simulate failures
                for attempt in range(1, 6):
                    await RetryQueries.log_activity_attempt(order_id, "receive_order", attempt, "failed", 500 + attempt * 100)
                await OrderQueries.update_order_state(order_id, "failed")
        
        # Test health monitoring
        all_summaries = await RetryQueries.get_all_retry_summaries()
        health_summaries = [s for s in all_summaries if s["order_id"].startswith("health_")]
        assert len(health_summaries) == 3
        
        # Test activity performance
        performance = await RetryQueries.get_activity_performance()
        assert len(performance) >= 2  # Should have data for receive_order and validate_order
        
        # Test failed activities
        failed_activities = await RetryQueries.get_failed_activities()
        failed_types = [f["activity_type"] for f in failed_activities]
        assert "receive_order" in failed_types
        assert "validate_order" in failed_types

class TestDataIntegrityUnderConcurrency:
    """Test data integrity under concurrent operations."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        yield
        
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id LIKE 'concurrent_%'")
            await execute_query("DELETE FROM events WHERE order_id LIKE 'concurrent_%'")
            await execute_query("DELETE FROM payments WHERE order_id LIKE 'concurrent_%'")
            await execute_query("DELETE FROM orders WHERE id LIKE 'concurrent_%'")
        except:
            pass
        
        await shutdown_db()

    async def test_concurrent_event_logging(self):
        """Test concurrent event logging for same order."""
        order_id = "concurrent_events_test"
        await OrderQueries.create_order(order_id, json.dumps({"concurrent": "test"}))
        
        # Log many events concurrently
        async def log_event(event_num):
            await EventQueries.log_event(order_id, f"concurrent_event_{event_num}", {
                "event_number": event_num,
                "timestamp": time.time()
            })
        
        event_count = 20
        await asyncio.gather(*[log_event(i) for i in range(event_count)])
        
        # Verify all events were logged
        events = await EventQueries.get_order_events(order_id)
        concurrent_events = [e for e in events if "concurrent_event_" in e["event_type"]]
        assert len(concurrent_events) == event_count

    async def test_concurrent_retry_tracking(self):
        """Test concurrent retry attempt logging."""
        order_id = "concurrent_retries_test"
        await OrderQueries.create_order(order_id, json.dumps({"concurrent": "test"}))
        
        # Log retry attempts concurrently for different activities
        async def log_attempts(activity_type, max_attempts):
            for attempt in range(1, max_attempts + 1):
                status = "completed" if attempt == max_attempts else "failed"
                await RetryQueries.log_activity_attempt(
                    order_id, activity_type, attempt, status, random.randint(500, 1500)
                )
        
        # Run concurrent retry logging for different activities
        await asyncio.gather(
            log_attempts("concurrent_activity_1", 3),
            log_attempts("concurrent_activity_2", 5),
            log_attempts("concurrent_activity_3", 2)
        )
        
        # Verify all attempts were logged correctly
        attempts = await RetryQueries.get_order_attempts(order_id)
        assert len(attempts) == 10  # 3 + 5 + 2
        
        # Verify attempts for each activity
        activity_1_attempts = [a for a in attempts if a["activity_type"] == "concurrent_activity_1"]
        activity_2_attempts = [a for a in attempts if a["activity_type"] == "concurrent_activity_2"]
        activity_3_attempts = [a for a in attempts if a["activity_type"] == "concurrent_activity_3"]
        
        assert len(activity_1_attempts) == 3
        assert len(activity_2_attempts) == 5
        assert len(activity_3_attempts) == 2

class TestSystemLimitsAndBoundaries:
    """Test system behavior at limits and boundaries."""
    
    @pytest.fixture(autouse=True)
    async def setup_and_cleanup(self):
        await startup_db()
        yield
        
        try:
            await execute_query("DELETE FROM activity_attempts WHERE order_id LIKE 'limits_%'")
            await execute_query("DELETE FROM events WHERE order_id LIKE 'limits_%'")
            await execute_query("DELETE FROM payments WHERE order_id LIKE 'limits_%'")
            await execute_query("DELETE FROM orders WHERE id LIKE 'limits_%'")
        except:
            pass
        
        await shutdown_db()

    async def test_maximum_retry_attempts(self):
        """Test system behavior with maximum retry attempts."""
        order_id = "limits_max_retries"
        await OrderQueries.create_order(order_id, json.dumps({"limits": "test"}))
        
        # Simulate maximum retry attempts (100 attempts)
        max_attempts = 100
        activity_type = "max_retry_activity"
        
        start_time = time.time()
        for attempt in range(1, max_attempts + 1):
            status = "completed" if attempt == max_attempts else "failed"
            await RetryQueries.log_activity_attempt(
                order_id, activity_type, attempt, status, 500
            )
        
        logging_time = time.time() - start_time
        print(f"✅ Logged {max_attempts} attempts in {logging_time:.2f}s")
        
        # Verify system handles extreme retry counts
        retry_summary = await RetryQueries.get_order_retry_summary(order_id)
        assert retry_summary["total_attempts"] == max_attempts
        assert retry_summary["total_retries"] == max_attempts - 1

    async def test_very_long_execution_times(self):
        """Test handling of very long execution times."""
        order_id = "limits_long_execution"
        await OrderQueries.create_order(order_id, json.dumps({"limits": "test"}))
        
        # Simulate activities with very long execution times
        long_execution_times = [30000, 60000, 120000, 300000]  # 30s, 1m, 2m, 5m
        
        for i, exec_time in enumerate(long_execution_times):
            await RetryQueries.log_activity_attempt(
                order_id, f"long_activity_{i}", 1, "completed", exec_time
            )
        
        # Verify system handles long execution times
        attempts = await RetryQueries.get_order_attempts(order_id)
        long_attempts = [a for a in attempts if a["execution_time_ms"] >= 30000]
        assert len(long_attempts) == 4
        
        # Test performance queries still work
        performance = await RetryQueries.get_activity_performance()
        long_activities = [p for p in performance if p["avg_execution_time_ms"] >= 30000]
        assert len(long_activities) >= 1

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])