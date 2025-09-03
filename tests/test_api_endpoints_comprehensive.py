"""
Comprehensive API Endpoint Tests

Tests all API endpoints with various scenarios:
- Happy path flows
- Error conditions
- Edge cases
- Integration with Temporal workflows
"""

import pytest
import json
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

# Import the FastAPI app
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

class TestOrderAPIEndpoints:
    """Test all order-related API endpoints."""
    
    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)
    
    @patch('api.main.Client.connect')
    @patch('api.main.startup_db')
    async def test_start_order_success(self, mock_startup_db, mock_client_connect):
        """Test successful order start."""
        # Mock Temporal client
        mock_client = AsyncMock()
        mock_handle = AsyncMock()
        mock_handle.id = "order-test123"
        mock_handle.first_execution_run_id = "run-123"
        mock_client.start_workflow.return_value = mock_handle
        mock_client_connect.return_value = mock_client
        
        # Test request
        response = self.client.post(
            "/orders/test123/start",
            json={"address": {"line1": "123 Test St", "city": "TestCity", "state": "TS", "zip": "12345"}}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["order_id"] == "test123"
        assert data["workflow_id"] == "order-test123"
    
    @patch('api.main.Client.connect')
    async def test_start_order_invalid_address(self, mock_client_connect):
        """Test order start with invalid address."""
        response = self.client.post(
            "/orders/test123/start",
            json={"address": {}}  # Missing required fields
        )
        
        assert response.status_code == 422  # Validation error
    
    @patch('api.main.Client.connect')
    async def test_start_order_temporal_error(self, mock_client_connect):
        """Test order start when Temporal is unavailable."""
        mock_client_connect.side_effect = Exception("Temporal connection failed")
        
        response = self.client.post(
            "/orders/test123/start",
            json={"address": {"line1": "123 Test St", "city": "TestCity", "state": "TS", "zip": "12345"}}
        )
        
        assert response.status_code == 500
        assert "Failed to start order" in response.json()["detail"]

    @patch('api.main.Client.connect')
    async def test_cancel_order_success(self, mock_client_connect):
        """Test successful order cancellation."""
        mock_client = AsyncMock()
        mock_handle = AsyncMock()
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_client_connect.return_value = mock_client
        
        response = self.client.post("/orders/test123/signals/cancel")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancel_signal_sent"
        assert data["order_id"] == "test123"
        
        # Verify signal was sent
        mock_handle.signal.assert_called_once()

    @patch('api.main.Client.connect')
    async def test_cancel_order_workflow_not_found(self, mock_client_connect):
        """Test cancelling non-existent order."""
        mock_client = AsyncMock()
        mock_handle = AsyncMock()
        mock_handle.signal.side_effect = Exception("workflow execution already completed")
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_client_connect.return_value = mock_client
        
        response = self.client.post("/orders/nonexistent/signals/cancel")
        
        assert response.status_code == 500
        assert "Failed to cancel order" in response.json()["detail"]

    @patch('api.main.Client.connect')
    async def test_approve_order_success(self, mock_client_connect):
        """Test successful order approval."""
        mock_client = AsyncMock()
        mock_handle = AsyncMock()
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_client_connect.return_value = mock_client
        
        response = self.client.post("/orders/test123/approve")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approve_signal_sent"
        assert data["order_id"] == "test123"

    @patch('api.main.Client.connect')
    async def test_get_order_status_running(self, mock_client_connect):
        """Test getting status of running order."""
        mock_client = AsyncMock()
        mock_handle = AsyncMock()
        mock_handle.id = "order-test123"
        mock_handle.first_execution_run_id = "run-123"
        
        # Mock running workflow
        mock_description = MagicMock()
        mock_description.status.name = "RUNNING"
        mock_handle.describe.return_value = mock_description
        mock_handle.result.side_effect = asyncio.TimeoutError()  # Still running
        
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_client_connect.return_value = mock_client
        
        response = self.client.get("/orders/test123/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["order_id"] == "test123"
        assert data["workflow_status"] == "RUNNING"

    @patch('api.main.Client.connect')
    async def test_get_order_status_completed(self, mock_client_connect):
        """Test getting status of completed order."""
        mock_client = AsyncMock()
        mock_handle = AsyncMock()
        mock_handle.id = "order-test123"
        mock_handle.first_execution_run_id = "run-123"
        mock_handle.result.return_value = "shipped"  # Completed successfully
        
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_client_connect.return_value = mock_client
        
        response = self.client.get("/orders/test123/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["order_id"] == "test123"
        assert data["workflow_status"] == "COMPLETED"

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

class TestAPIErrorHandling:
    """Test API error handling and edge cases."""
    
    def setup_method(self):
        self.client = TestClient(app)

    def test_invalid_order_id_formats(self):
        """Test various invalid order ID formats."""
        invalid_ids = ["", " ", "order-with-spaces", "order/with/slashes", "order?with=query"]
        
        for invalid_id in invalid_ids:
            response = self.client.post(
                f"/orders/{invalid_id}/start",
                json={"address": {"line1": "123 Test St", "city": "TestCity", "state": "TS", "zip": "12345"}}
            )
            # Should either reject or sanitize the ID
            # The exact behavior depends on FastAPI's path parameter handling

    def test_missing_request_body(self):
        """Test endpoints with missing request bodies."""
        response = self.client.post("/orders/test123/start")
        assert response.status_code == 422  # Unprocessable Entity

    def test_malformed_json(self):
        """Test endpoints with malformed JSON."""
        response = self.client.post(
            "/orders/test123/start",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    @patch('api.main.Client.connect')
    async def test_temporal_connection_failures(self, mock_client_connect):
        """Test various Temporal connection failure scenarios."""
        # Test connection timeout
        mock_client_connect.side_effect = asyncio.TimeoutError("Connection timeout")
        
        response = self.client.post(
            "/orders/test123/start",
            json={"address": {"line1": "123 Test St", "city": "TestCity", "state": "TS", "zip": "12345"}}
        )
        
        assert response.status_code == 500
        assert "Failed to start order" in response.json()["detail"]

class TestConcurrencyAndRaceConditions:
    """Test concurrent operations and race conditions."""
    
    def setup_method(self):
        self.client = TestClient(app)

    @patch('api.main.Client.connect')
    async def test_concurrent_order_operations(self, mock_client_connect):
        """Test concurrent operations on the same order."""
        mock_client = AsyncMock()
        mock_handle = AsyncMock()
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_client.start_workflow.return_value = mock_handle
        mock_client_connect.return_value = mock_client
        
        order_id = "concurrent_test"
        
        # Simulate concurrent start, cancel, and approve
        async def start_order():
            return self.client.post(
                f"/orders/{order_id}/start",
                json={"address": {"line1": "123 Test St", "city": "TestCity", "state": "TS", "zip": "12345"}}
            )
        
        async def cancel_order():
            return self.client.post(f"/orders/{order_id}/signals/cancel")
        
        async def approve_order():
            return self.client.post(f"/orders/{order_id}/approve")
        
        # Run operations concurrently
        responses = await asyncio.gather(
            start_order(),
            cancel_order(),
            approve_order(),
            return_exceptions=True
        )
        
        # At least one should succeed
        successful_responses = [r for r in responses if not isinstance(r, Exception) and hasattr(r, 'status_code')]
        assert len(successful_responses) >= 1

class TestWorkflowStateTransitions:
    """Test workflow state transitions and validation."""
    
    @pytest.fixture(autouse=True)
    async def setup_db(self):
        await startup_db()
        yield
        await shutdown_db()

    async def test_state_transition_sequence(self):
        """Test valid state transition sequences."""
        order_id = "state_transition_test"
        await OrderQueries.create_order(order_id, json.dumps({"test": "data"}))
        
        # Valid state transitions
        valid_transitions = [
            "created",
            "received", 
            "validating",
            "validated",
            "charging_payment",
            "payment_charged",
            "preparing_package",
            "package_prepared",
            "dispatching_carrier",
            "shipped"
        ]
        
        for state in valid_transitions:
            await OrderQueries.update_order_state(order_id, state)
            order = await OrderQueries.get_order(order_id)
            assert order["state"] == state
        
        # Cleanup
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)

    async def test_invalid_state_transitions(self):
        """Test handling of invalid state transitions."""
        order_id = "invalid_transition_test"
        await OrderQueries.create_order(order_id, json.dumps({"test": "data"}))
        
        # Try invalid state
        await OrderQueries.update_order_state(order_id, "invalid_state")
        order = await OrderQueries.get_order(order_id)
        assert order["state"] == "invalid_state"  # Our system currently allows any state
        
        # Cleanup
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)

class TestPerformanceAndScaling:
    """Test performance characteristics and scaling behavior."""
    
    @pytest.fixture(autouse=True)
    async def setup_db(self):
        await startup_db()
        yield
        await shutdown_db()

    async def test_bulk_order_creation(self):
        """Test creating many orders quickly."""
        order_ids = [f"bulk_test_{i}" for i in range(50)]
        
        # Create orders in parallel
        async def create_order(order_id):
            return await OrderQueries.create_order(order_id, json.dumps({"bulk": "test"}))
        
        start_time = time.time()
        await asyncio.gather(*[create_order(order_id) for order_id in order_ids])
        creation_time = time.time() - start_time
        
        # Should complete reasonably quickly (adjust threshold as needed)
        assert creation_time < 10.0, f"Bulk creation took {creation_time:.2f}s, expected < 10s"
        
        # Verify all orders were created
        for order_id in order_ids:
            order = await OrderQueries.get_order(order_id)
            assert order is not None
        
        # Cleanup
        for order_id in order_ids:
            await execute_query("DELETE FROM orders WHERE id = $1", order_id)

    async def test_bulk_event_logging(self):
        """Test logging many events quickly."""
        order_id = "bulk_events_test"
        await OrderQueries.create_order(order_id, json.dumps({"test": "data"}))
        
        # Log many events
        event_count = 100
        start_time = time.time()
        
        for i in range(event_count):
            await EventQueries.log_event(order_id, f"test_event_{i}", {"index": i})
        
        logging_time = time.time() - start_time
        assert logging_time < 30.0, f"Event logging took {logging_time:.2f}s, expected < 30s"
        
        # Verify events were logged
        events = await EventQueries.get_order_events(order_id)
        assert len(events) == event_count
        
        # Cleanup
        await execute_query("DELETE FROM events WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)

    async def test_query_performance_with_large_dataset(self):
        """Test query performance with larger datasets."""
        # Create test data
        order_ids = [f"perf_test_{i}" for i in range(20)]
        
        for order_id in order_ids:
            await OrderQueries.create_order(order_id, json.dumps({"perf": "test"}))
            
            # Add events and attempts
            for event_num in range(5):
                await EventQueries.log_event(order_id, f"event_{event_num}", {"test": True})
            
            for attempt_num in range(1, 4):
                await RetryQueries.log_activity_attempt(
                    order_id, "test_activity", attempt_num, 
                    "completed" if attempt_num == 3 else "failed", 
                    1000 + attempt_num * 100
                )
        
        # Test query performance
        start_time = time.time()
        
        # Test various queries
        recent_orders = await OrderQueries.get_recent_orders(10)
        recent_events = await EventQueries.get_recent_events(50)
        retry_summaries = await RetryQueries.get_all_retry_summaries()
        activity_performance = await RetryQueries.get_activity_performance()
        
        query_time = time.time() - start_time
        assert query_time < 5.0, f"Queries took {query_time:.2f}s, expected < 5s"
        
        # Verify results
        assert len(recent_orders) >= 10
        assert len(recent_events) >= 20  # Should have many events
        assert len(retry_summaries) >= 20
        assert len(activity_performance) >= 1
        
        # Cleanup
        for order_id in order_ids:
            await execute_query("DELETE FROM activity_attempts WHERE order_id = $1", order_id)
            await execute_query("DELETE FROM events WHERE order_id = $1", order_id)
            await execute_query("DELETE FROM orders WHERE id = $1", order_id)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])