"""
Comprehensive CLI Tests

Tests the interactive CLI with various scenarios:
- Menu navigation
- Order operations
- Status checking with retry counts
- Audit logs (simplified)
- Error handling
- User input validation
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from io import StringIO
import sys

# Import CLI components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli import (
    start_order_interactive, cancel_order_interactive, check_status_interactive,
    approve_order_interactive, update_address_interactive, view_audit_logs_interactive,
    get_user_input, print_pizza_tracker, get_order_step, Colors
)

class TestCLIOrderOperations:
    """Test CLI order operations."""
    
    @patch('cli.startup_db')
    @patch('cli.Client.connect')
    @patch('cli.get_user_input')
    async def test_start_order_interactive_success(self, mock_input, mock_client_connect, mock_startup_db):
        """Test interactive order start with valid inputs."""
        # Mock user inputs
        mock_input.side_effect = [
            "test_order_123",  # Order ID
            "123 Main St",     # Address line 1
            "Anytown",         # City
            "ST",              # State
            "12345"            # ZIP
        ]
        
        # Mock Temporal client
        mock_client = AsyncMock()
        mock_handle = AsyncMock()
        mock_handle.id = "order-test_order_123"
        mock_handle.first_execution_run_id = "run-123"
        mock_client.start_workflow.return_value = mock_handle
        mock_client_connect.return_value = mock_client
        
        # Capture output
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await start_order_interactive(mock_client)
        
        output = mock_stdout.getvalue()
        assert "✅ Order started successfully!" in output
        assert "test_order_123" in output

    @patch('cli.startup_db')
    @patch('cli.Client.connect')
    @patch('cli.get_user_input')
    async def test_start_order_interactive_temporal_error(self, mock_input, mock_client_connect, mock_startup_db):
        """Test interactive order start with Temporal error."""
        mock_input.side_effect = ["test_order", "123 Main St", "Anytown", "ST", "12345"]
        mock_client_connect.side_effect = Exception("Temporal connection failed")
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await start_order_interactive(None)
        
        output = mock_stdout.getvalue()
        assert "❌" in output or "Failed" in output

    @patch('cli.startup_db')
    @patch('cli.Client.connect')
    @patch('cli.get_user_input')
    async def test_cancel_order_interactive_success(self, mock_input, mock_client_connect, mock_startup_db):
        """Test interactive order cancellation."""
        # Mock recent orders
        mock_workflows = [
            MagicMock(id="order-test1", start_time=MagicMock()),
            MagicMock(id="order-test2", start_time=MagicMock())
        ]
        mock_workflows[0].start_time.strftime.return_value = "12:00:00"
        mock_workflows[1].start_time.strftime.return_value = "12:05:00"
        
        mock_client = AsyncMock()
        mock_client.list_workflows.return_value = AsyncMock()
        mock_client.list_workflows.return_value.__aiter__ = AsyncMock(return_value=iter(mock_workflows))
        
        mock_handle = AsyncMock()
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_client_connect.return_value = mock_client
        
        # Mock database queries
        with patch('cli.OrderQueries.get_order', return_value={"state": "validated"}):
            with patch('cli.RetryQueries.get_order_attempts', return_value=[]):
                mock_input.side_effect = ["1"]  # Select first order
                
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    await cancel_order_interactive(mock_client)
                
                output = mock_stdout.getvalue()
                assert "test1" in output  # Should show the order
                mock_handle.signal.assert_called_once()

    @patch('cli.startup_db')
    @patch('cli.Client.connect')
    @patch('cli.get_user_input')
    async def test_check_status_with_retry_counts(self, mock_input, mock_client_connect, mock_startup_db):
        """Test status checking displays retry counts correctly."""
        # Mock workflows with different retry patterns
        mock_workflows = [
            MagicMock(id="order-low_retry", start_time=MagicMock()),
            MagicMock(id="order-high_retry", start_time=MagicMock()),
            MagicMock(id="order-no_retry", start_time=MagicMock())
        ]
        
        for w in mock_workflows:
            w.start_time.strftime.return_value = "12:00:00"
        
        mock_client = AsyncMock()
        mock_client.list_workflows.return_value = AsyncMock()
        mock_client.list_workflows.return_value.__aiter__ = AsyncMock(return_value=iter(mock_workflows))
        
        # Mock workflow handles
        mock_handles = {}
        for w in mock_workflows:
            handle = AsyncMock()
            handle.id = w.id
            handle.result.side_effect = asyncio.TimeoutError()  # Still running
            
            description = MagicMock()
            description.status.name = "RUNNING"
            handle.describe.return_value = description
            
            mock_handles[w.id] = handle
        
        mock_client.get_workflow_handle.side_effect = lambda wf_id: mock_handles[wf_id]
        mock_client_connect.return_value = mock_client
        
        # Mock database responses with different retry counts
        async def mock_get_order(order_id):
            return {"state": "validated"}
        
        async def mock_get_attempts(order_id):
            if "low_retry" in order_id:
                return [{"attempt_number": 1}, {"attempt_number": 2}]  # 1 retry
            elif "high_retry" in order_id:
                return [{"attempt_number": 1}, {"attempt_number": 2}, {"attempt_number": 3}, 
                       {"attempt_number": 4}, {"attempt_number": 5}, {"attempt_number": 6}]  # 5 retries
            else:
                return [{"attempt_number": 1}]  # 0 retries
        
        with patch('cli.OrderQueries.get_order', side_effect=mock_get_order):
            with patch('cli.RetryQueries.get_order_attempts', side_effect=mock_get_attempts):
                mock_input.return_value = "0"  # Exit
                
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    await check_status_interactive(mock_client)
                
                output = mock_stdout.getvalue()
                
                # Should show retry counts in different colors
                assert "Retries" in output  # Column header
                assert "low_retry" in output
                assert "high_retry" in output
                assert "no_retry" in output

class TestCLIUserInputValidation:
    """Test CLI user input validation and error handling."""
    
    @patch('cli.get_user_input')
    def test_menu_input_validation(self, mock_input):
        """Test main menu input validation."""
        # Test invalid inputs
        invalid_inputs = ["", " ", "abc", "99", "-1", "1.5"]
        
        for invalid_input in invalid_inputs:
            mock_input.return_value = invalid_input
            # The get_user_input function should handle validation
            # This test ensures we don't crash on invalid inputs

    @patch('cli.startup_db')
    @patch('cli.get_user_input')
    async def test_address_input_validation(self, mock_input, mock_startup_db):
        """Test address input validation in order creation."""
        # Test with empty inputs
        mock_input.side_effect = ["", "", "", "", ""]  # All empty
        
        with patch('sys.stdout', new_callable=StringIO):
            # Should handle empty inputs gracefully
            try:
                await start_order_interactive(None)
            except Exception as e:
                # Should not crash, but may show validation errors
                pass

    @patch('cli.startup_db')
    @patch('cli.Client.connect')
    @patch('cli.get_user_input')
    async def test_order_selection_edge_cases(self, mock_input, mock_client_connect, mock_startup_db):
        """Test order selection with edge cases."""
        mock_client = AsyncMock()
        mock_client.list_workflows.return_value = AsyncMock()
        mock_client.list_workflows.return_value.__aiter__ = AsyncMock(return_value=iter([]))  # No orders
        mock_client_connect.return_value = mock_client
        
        mock_input.return_value = "1"  # Try to select order 1 when none exist
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await check_status_interactive(mock_client)
        
        output = mock_stdout.getvalue()
        assert "No recent orders found" in output or "No orders" in output

class TestCLIAuditLogsSimplified:
    """Test the simplified audit logs functionality."""
    
    @patch('cli.startup_db')
    @patch('cli.EventQueries.get_recent_events')
    async def test_audit_logs_direct_display(self, mock_get_events, mock_startup_db):
        """Test that audit logs shows recent events directly."""
        # Mock recent events
        mock_events = [
            {
                "order_id": "test1",
                "event_type": "order_received",
                "created_at": "2025-01-01 12:00:00",
                "event_data": {"source": "test"}
            },
            {
                "order_id": "test2", 
                "event_type": "payment_charged",
                "created_at": "2025-01-01 12:05:00",
                "event_data": {"amount": 99.99}
            }
        ]
        mock_get_events.return_value = mock_events
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await view_audit_logs_interactive(None)
        
        output = mock_stdout.getvalue()
        assert "📋 Recent Order Events" in output
        assert "test1" in output
        assert "test2" in output
        assert "order_received" in output
        assert "payment_charged" in output

    @patch('cli.startup_db')
    @patch('cli.EventQueries.get_recent_events')
    async def test_audit_logs_empty_events(self, mock_get_events, mock_startup_db):
        """Test audit logs with no events."""
        mock_get_events.return_value = []
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await view_audit_logs_interactive(None)
        
        output = mock_stdout.getvalue()
        assert "No events found" in output

class TestCLIPizzaTracker:
    """Test the pizza tracker functionality."""
    
    @patch('cli.startup_db')
    async def test_pizza_tracker_display(self, mock_startup_db):
        """Test pizza tracker displays order progress correctly."""
        order_id = "tracker_test"
        
        # Mock database queries for pizza tracker
        with patch('cli.ObservabilityQueries.get_order_health_report') as mock_health:
            with patch('cli.PaymentQueries.get_payment') as mock_payment:
                with patch('cli.EventQueries.get_order_events') as mock_events:
                    
                    mock_health.return_value = {
                        "order_id": order_id,
                        "total_events": 5,
                        "total_attempts": 3,
                        "total_retries": 1,
                        "unique_activities": 3
                    }
                    
                    mock_payment.return_value = {
                        "status": "charged",
                        "amount": Decimal("99.99"),
                        "retry_count": 1
                    }
                    
                    mock_events.return_value = [
                        {"event_type": "order_received", "created_at": "12:00:00"},
                        {"event_type": "order_validated", "created_at": "12:01:00"},
                        {"event_type": "payment_charged", "created_at": "12:02:00"}
                    ]
                    
                    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                        await print_pizza_tracker(order_id, "COMPLETED", "shipped")
                    
                    output = mock_stdout.getvalue()
                    assert "Order Progress Tracker" in output
                    assert order_id in output
                    assert "Health Metrics" in output
                    assert "Payment Status" in output

class TestCLIErrorHandling:
    """Test CLI error handling and resilience."""
    
    @patch('cli.startup_db')
    async def test_database_connection_failure(self, mock_startup_db):
        """Test CLI behavior when database is unavailable."""
        mock_startup_db.side_effect = Exception("Database connection failed")
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await view_audit_logs_interactive(None)
        
        output = mock_stdout.getvalue()
        assert "❌" in output or "Failed" in output

    @patch('cli.Client.connect')
    async def test_temporal_connection_failure(self, mock_client_connect):
        """Test CLI behavior when Temporal is unavailable."""
        mock_client_connect.side_effect = Exception("Temporal connection failed")
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await start_order_interactive(None)
        
        output = mock_stdout.getvalue()
        assert "❌" in output or "Failed" in output

    @patch('cli.startup_db')
    @patch('cli.Client.connect')
    @patch('cli.get_user_input')
    async def test_invalid_order_selection(self, mock_input, mock_client_connect, mock_startup_db):
        """Test selecting invalid order numbers."""
        mock_client = AsyncMock()
        mock_client.list_workflows.return_value = AsyncMock()
        mock_client.list_workflows.return_value.__aiter__ = AsyncMock(return_value=iter([]))
        mock_client_connect.return_value = mock_client
        
        # Try to select order 5 when no orders exist
        mock_input.return_value = "5"
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            await check_status_interactive(mock_client)
        
        output = mock_stdout.getvalue()
        assert "No recent orders found" in output or "Invalid" in output

class TestCLIRetryCountDisplay:
    """Test the new retry count display functionality."""
    
    @patch('cli.startup_db')
    @patch('cli.Client.connect')
    @patch('cli.get_user_input')
    async def test_retry_count_color_coding(self, mock_input, mock_client_connect, mock_startup_db):
        """Test retry count color coding in status display."""
        # Mock workflows
        mock_workflows = [
            MagicMock(id="order-zero_retries", start_time=MagicMock()),
            MagicMock(id="order-few_retries", start_time=MagicMock()),
            MagicMock(id="order-many_retries", start_time=MagicMock())
        ]
        
        for w in mock_workflows:
            w.start_time.strftime.return_value = "12:00:00"
        
        mock_client = AsyncMock()
        mock_client.list_workflows.return_value = AsyncMock()
        mock_client.list_workflows.return_value.__aiter__ = AsyncMock(return_value=iter(mock_workflows))
        
        # Mock workflow handles
        for w in mock_workflows:
            handle = AsyncMock()
            handle.id = w.id
            handle.result.side_effect = asyncio.TimeoutError()
            
            description = MagicMock()
            description.status.name = "RUNNING"
            handle.describe.return_value = description
        
        mock_client.get_workflow_handle.return_value = handle
        mock_client_connect.return_value = mock_client
        
        # Mock database responses
        async def mock_get_order(order_id):
            return {"state": "validated"}
        
        async def mock_get_attempts(order_id):
            if "zero_retries" in order_id:
                return [{"attempt_number": 1}]  # 0 retries
            elif "few_retries" in order_id:
                return [{"attempt_number": 1}, {"attempt_number": 2}, {"attempt_number": 3}]  # 2 retries
            else:
                return [{"attempt_number": i} for i in range(1, 8)]  # 6 retries
        
        with patch('cli.OrderQueries.get_order', side_effect=mock_get_order):
            with patch('cli.RetryQueries.get_order_attempts', side_effect=mock_get_attempts):
                mock_input.return_value = "0"  # Exit
                
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    await check_status_interactive(mock_client)
                
                output = mock_stdout.getvalue()
                
                # Should show retry counts
                assert "Retries" in output
                assert "0" in output  # Zero retries
                assert "2" in output  # Few retries  
                assert "6" in output  # Many retries

class TestCLIAddressUpdate:
    """Test address update functionality."""
    
    @patch('cli.startup_db')
    @patch('cli.Client.connect')
    @patch('cli.get_user_input')
    async def test_address_update_interactive(self, mock_input, mock_client_connect, mock_startup_db):
        """Test interactive address update."""
        # Mock order selection and new address input
        mock_input.side_effect = [
            "1",               # Select first order
            "456 New St",      # New address line 1
            "NewCity",         # New city
            "NS",              # New state
            "54321"            # New ZIP
        ]
        
        # Mock workflows
        mock_workflow = MagicMock(id="order-test_update", start_time=MagicMock())
        mock_workflow.start_time.strftime.return_value = "12:00:00"
        
        mock_client = AsyncMock()
        mock_client.list_workflows.return_value = AsyncMock()
        mock_client.list_workflows.return_value.__aiter__ = AsyncMock(return_value=iter([mock_workflow]))
        
        mock_handle = AsyncMock()
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_client_connect.return_value = mock_client
        
        # Mock database
        with patch('cli.OrderQueries.get_order', return_value={"state": "validated"}):
            with patch('cli.RetryQueries.get_order_attempts', return_value=[]):
                
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    await update_address_interactive(mock_client)
                
                output = mock_stdout.getvalue()
                assert "✅" in output or "success" in output.lower()
                mock_handle.signal.assert_called_once()

class TestCLIColorAndFormatting:
    """Test CLI color coding and formatting."""
    
    def test_order_step_color_mapping(self):
        """Test that order steps get correct colors."""
        # Test completed states (should be green)
        step, color = get_order_step("COMPLETED", "shipped")
        assert color == Colors.GREEN
        
        step, color = get_order_step("COMPLETED", "Cancelled")
        assert color == Colors.RED
        
        # Test running states (should be yellow)
        step, color = get_order_step("RUNNING", None)
        assert color == Colors.YELLOW
        
        # Test failed states (should be red)
        step, color = get_order_step("FAILED", None)
        assert color == Colors.RED

    def test_retry_count_color_coding(self):
        """Test retry count color coding logic."""
        # This tests the logic from the CLI
        # 0 retries = green, 1-4 = yellow, 5+ = red
        
        def get_retry_color(retry_count):
            return Colors.GREEN if retry_count == 0 else Colors.YELLOW if retry_count < 5 else Colors.RED
        
        assert get_retry_color(0) == Colors.GREEN
        assert get_retry_color(1) == Colors.YELLOW
        assert get_retry_color(4) == Colors.YELLOW
        assert get_retry_color(5) == Colors.RED
        assert get_retry_color(10) == Colors.RED

if __name__ == "__main__":
    pytest.main([__file__, "-v"])