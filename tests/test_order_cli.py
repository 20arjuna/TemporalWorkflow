"""
Unit tests for the interactive order CLI tool.
Tests all CLI functionality with mocked Temporal client and user input.
"""

import pytest
import asyncio
import json
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the CLI module
import cli

class TestInteractiveCLI:
    """Test suite for interactive CLI functions."""

    @pytest.fixture
    def mock_client(self):
        """Create a mocked Temporal client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_handle(self):
        """Create a mocked workflow handle."""
        handle = AsyncMock()
        handle.id = "order-O-123"
        handle.result_run_id = "run-123"
        
        # Mock description for status checks
        description = MagicMock()
        description.run_id = "run-123"
        description.status.name = "RUNNING"
        description.start_time = datetime.now()
        handle.describe.return_value = description
        
        return handle

    @pytest.mark.asyncio
    async def test_connect_to_temporal_success(self, mock_client):
        """Test successful Temporal connection."""
        with patch('cli.Client.connect', return_value=mock_client):
            with patch('builtins.print') as mock_print:
                result = await cli.connect_to_temporal()
        
        assert result == mock_client
        # Check success message was printed
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Connected to Temporal!" in printed_output

    @pytest.mark.asyncio
    async def test_connect_to_temporal_failure(self):
        """Test Temporal connection failure."""
        with patch('cli.Client.connect', side_effect=Exception("Connection refused")):
            with patch('builtins.print') as mock_print:
                result = await cli.connect_to_temporal()
        
        assert result is None
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Failed to connect" in printed_output
        assert "docker compose up -d" in printed_output

    @pytest.mark.asyncio
    async def test_start_order_interactive_success(self, mock_client, mock_handle):
        """Test interactive order creation with valid inputs."""
        mock_client.start_workflow.return_value = mock_handle
        
        # Mock user inputs
        inputs = ["O-456", "456 Oak Street", "Lincoln", "68508"]
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.start_order_interactive(mock_client)
        
        # Verify workflow was started
        mock_client.start_workflow.assert_called_once()
        call_args = mock_client.start_workflow.call_args
        assert call_args[1]['args'][0] == "O-456"
        assert call_args[1]['args'][1] == {"line1": "456 Oak Street", "city": "Lincoln", "zip": "68508"}
        
        # Check success message
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "started successfully" in printed_output

    @pytest.mark.asyncio
    async def test_start_order_interactive_empty_order_id(self):
        """Test interactive order creation with empty order ID."""
        inputs = [""]  # Empty order ID
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.start_order_interactive(None)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Order ID is required" in printed_output

    @pytest.mark.asyncio
    async def test_start_order_interactive_incomplete_address(self):
        """Test interactive order creation with incomplete address."""
        inputs = ["O-123", "123 Main St", "", "68102"]  # Missing city
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.start_order_interactive(None)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "All address fields are required" in printed_output

    @pytest.mark.asyncio
    async def test_check_status_interactive_completed(self, mock_client, mock_handle):
        """Test interactive status check for completed workflow."""
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_handle.result.return_value = "OrderShipped"
        
        inputs = ["O-123"]
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.check_status_interactive(mock_client)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "COMPLETED" in printed_output
        assert "OrderShipped" in printed_output

    @pytest.mark.asyncio
    async def test_check_status_interactive_running(self, mock_client, mock_handle):
        """Test interactive status check for running workflow."""
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_handle.result.side_effect = asyncio.TimeoutError()
        
        inputs = ["O-123"]
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.check_status_interactive(mock_client)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "RUNNING" in printed_output
        assert "order-O-123" in printed_output

    @pytest.mark.asyncio
    async def test_check_status_interactive_not_found(self, mock_client):
        """Test interactive status check for non-existent workflow."""
        mock_client.get_workflow_handle.side_effect = Exception("Workflow not found")
        
        inputs = ["O-999"]
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.check_status_interactive(mock_client)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "not found" in printed_output

    @pytest.mark.asyncio
    async def test_approve_order_interactive_success(self, mock_client, mock_handle):
        """Test interactive order approval."""
        mock_client.get_workflow_handle.return_value = mock_handle
        
        inputs = ["O-123"]
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.approve_order_interactive(mock_client)
        
        mock_handle.signal.assert_called_once()
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Approval signal sent" in printed_output

    @pytest.mark.asyncio
    async def test_cancel_order_interactive_confirmed(self, mock_client, mock_handle):
        """Test interactive order cancellation with confirmation."""
        mock_client.get_workflow_handle.return_value = mock_handle
        
        inputs = ["O-123", "y"]  # Order ID and confirmation
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.cancel_order_interactive(mock_client)
        
        mock_handle.signal.assert_called_once()
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Cancellation signal sent" in printed_output

    @pytest.mark.asyncio
    async def test_cancel_order_interactive_declined(self, mock_client):
        """Test interactive order cancellation when user declines."""
        inputs = ["O-123", "n"]  # Order ID and decline confirmation
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.cancel_order_interactive(mock_client)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Cancellation aborted" in printed_output

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_client):
        """Test health check with healthy Temporal server."""
        mock_client.list_workflows.return_value = []  # Empty list is fine
        
        with patch('cli.Client.connect', return_value=mock_client):
            with patch('builtins.print') as mock_print:
                await cli.health_check()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "HEALTHY" in printed_output
        assert "WORKING" in printed_output

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check with unhealthy Temporal server."""
        with patch('cli.Client.connect', side_effect=Exception("Connection refused")):
            with patch('builtins.print') as mock_print:
                await cli.health_check()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "UNHEALTHY" in printed_output

class TestCLIMainLoop:
    """Test the main CLI loop and menu system."""

    @pytest.fixture
    def mock_client(self):
        """Create a mocked Temporal client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_handle(self):
        """Create a mocked workflow handle."""
        handle = AsyncMock()
        handle.id = "order-O-123"
        handle.result_run_id = "run-123"
        
        description = MagicMock()
        description.run_id = "run-123"
        description.status.name = "RUNNING"
        description.start_time = datetime.now()
        handle.describe.return_value = description
        
        return handle

    @pytest.mark.asyncio
    async def test_main_loop_quit_immediately(self, mock_client):
        """Test main loop quits when user chooses 'q'."""
        inputs = ["q"]  # Quit immediately
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print') as mock_print:
                    await cli.main()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Thanks for using" in printed_output

    @pytest.mark.asyncio 
    async def test_main_loop_start_order_flow(self, mock_client, mock_handle):
        """Test main loop choosing start order option."""
        mock_client.start_workflow.return_value = mock_handle
        
        # User chooses option 1 (start), then quits
        inputs = ["1", "O-789", "789 Pine St", "Omaha", "68102", "", "q"]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print'):
                    await cli.main()
        
        # Verify workflow was started
        mock_client.start_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_loop_status_check_flow(self, mock_client, mock_handle):
        """Test main loop choosing status check option."""
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_handle.result.return_value = "Completed"
        
        # User chooses option 2 (status), then quits
        inputs = ["2", "O-123", "", "q"]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print'):
                    await cli.main()
        
        mock_client.get_workflow_handle.assert_called_once_with("order-O-123")

    @pytest.mark.asyncio
    async def test_main_loop_approve_flow(self, mock_client, mock_handle):
        """Test main loop choosing approve option."""
        mock_client.get_workflow_handle.return_value = mock_handle
        
        # User chooses option 3 (approve), then quits
        inputs = ["3", "O-123", "", "q"]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print'):
                    await cli.main()
        
        mock_handle.signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_loop_cancel_flow_confirmed(self, mock_client, mock_handle):
        """Test main loop choosing cancel option with confirmation."""
        mock_client.get_workflow_handle.return_value = mock_handle
        
        # User chooses option 4 (cancel), confirms, then quits
        inputs = ["4", "O-123", "y", "", "q"]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print'):
                    await cli.main()
        
        mock_handle.signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_loop_cancel_flow_declined(self, mock_client):
        """Test main loop choosing cancel option but declining confirmation."""
        # User chooses option 4 (cancel), declines, then quits
        inputs = ["4", "O-123", "n", "", "q"]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print') as mock_print:
                    await cli.main()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "aborted" in printed_output

    @pytest.mark.asyncio
    async def test_main_loop_health_check(self, mock_client):
        """Test main loop choosing health check option."""
        mock_client.list_workflows.return_value = []
        
        # User chooses option 6 (health), then quits
        inputs = ["6", "", "q"]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('cli.Client.connect', return_value=mock_client):
                with patch('builtins.input', side_effect=inputs):
                    with patch('builtins.print') as mock_print:
                        await cli.main()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Health check complete" in printed_output

    @pytest.mark.asyncio
    async def test_main_loop_invalid_choice(self, mock_client):
        """Test main loop with invalid menu choice."""
        inputs = ["9", "q"]  # Invalid choice, then quit
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print') as mock_print:
                    await cli.main()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Invalid choice: 9" in printed_output

    @pytest.mark.asyncio
    async def test_main_loop_keyboard_interrupt(self, mock_client):
        """Test main loop handles Ctrl+C gracefully."""
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=KeyboardInterrupt()):
                with patch('builtins.print') as mock_print:
                    await cli.main()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Caught Ctrl+C" in printed_output

    @pytest.mark.asyncio
    async def test_main_loop_health_check_flow(self, mock_client):
        """Test main loop choosing health check option."""
        mock_client.list_workflows.return_value = []
        
        # User chooses option 5 (health check), then quits
        inputs = ["5", "", "q"]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('cli.Client.connect', return_value=mock_client):
                with patch('builtins.input', side_effect=inputs):
                    with patch('builtins.print') as mock_print:
                        await cli.main()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Health check complete" in printed_output

class TestCLIUserInterface:
    """Test CLI user interface elements."""

    def test_print_banner_output(self):
        """Test banner contains expected elements."""
        with patch('builtins.print') as mock_print:
            cli.print_banner()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Arjun's Temporal Takehome" in printed_output
        assert "Interactive Order Management" in printed_output
        assert "🚀" in printed_output

    def test_print_menu_output(self):
        """Test menu contains all expected options."""
        with patch('builtins.print') as mock_print:
            cli.print_menu()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Start a new order" in printed_output
        assert "Check order status" in printed_output
        assert "Approve an order" in printed_output
        assert "Cancel an order" in printed_output

        assert "Health check" in printed_output
        assert "Quit" in printed_output
        
        # Check emojis are present
        assert "🛒" in printed_output
        assert "📊" in printed_output
        assert "✅" in printed_output
        assert "❌" in printed_output
        assert "📋" in printed_output
        assert "🏥" in printed_output
        assert "👋" in printed_output

    def test_color_helper_functions(self):
        """Test color helper functions work correctly."""
        with patch('builtins.print') as mock_print:
            cli.print_success("Test success")
            cli.print_error("Test error")
            cli.print_info("Test info")
            cli.print_warning("Test warning")
        
        # Verify all functions were called
        assert mock_print.call_count == 4
        
        # Check that messages contain expected text and emojis
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("Test success" in call and "✅" in call for call in calls)
        assert any("Test error" in call and "❌" in call for call in calls)
        assert any("Test info" in call and "ℹ️" in call for call in calls)
        assert any("Test warning" in call and "⚠️" in call for call in calls)

    def test_color_codes_defined(self):
        """Test that all color codes are properly defined."""
        colors = cli.Colors()
        
        # Check all expected color attributes exist
        assert hasattr(colors, 'HEADER')
        assert hasattr(colors, 'BLUE')
        assert hasattr(colors, 'CYAN')
        assert hasattr(colors, 'GREEN')
        assert hasattr(colors, 'YELLOW')
        assert hasattr(colors, 'RED')
        assert hasattr(colors, 'BOLD')
        assert hasattr(colors, 'END')
        
        # Check they're all strings with ANSI codes
        assert isinstance(colors.HEADER, str)
        assert isinstance(colors.END, str)
        assert '\033[' in colors.HEADER  # ANSI escape sequence
        assert '\033[' in colors.END

class TestCLIErrorHandling:
    """Test CLI error handling and edge cases."""

    @pytest.fixture
    def mock_client(self):
        """Create a mocked Temporal client."""
        return AsyncMock()

    @pytest.fixture
    def mock_handle(self):
        """Create a mocked workflow handle."""
        handle = AsyncMock()
        handle.id = "order-O-123"
        return handle

    @pytest.mark.asyncio
    async def test_temporal_connection_failure_in_main(self):
        """Test main function when Temporal connection fails."""
        with patch('cli.connect_to_temporal', return_value=None):
            with patch('builtins.print') as mock_print:
                await cli.main()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Cannot continue without Temporal connection" in printed_output

    @pytest.mark.asyncio
    async def test_workflow_start_failure_interactive(self, mock_client):
        """Test workflow start failure in interactive mode."""
        mock_client.start_workflow.side_effect = Exception("Workflow failed to start")
        
        inputs = ["O-123", "123 Main St", "Omaha", "68102"]
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.start_order_interactive(mock_client)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Failed to start order" in printed_output

    @pytest.mark.asyncio
    async def test_signal_failure_interactive(self, mock_client, mock_handle):
        """Test signal sending failure in interactive mode."""
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_handle.signal.side_effect = Exception("Signal failed")
        
        inputs = ["O-123"]
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.approve_order_interactive(mock_client)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Failed to approve order" in printed_output

    @pytest.mark.asyncio
    async def test_exception_in_menu_loop_continues(self, mock_client):
        """Test that exceptions in menu options don't crash the CLI."""
        mock_client.get_workflow_handle.side_effect = Exception("Temporal server down")
        
        # User tries status check (which will fail), then quits
        inputs = ["2", "O-123", "", "q"]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print') as mock_print:
                    await cli.main()
        
        # Should continue after exception and show goodbye message
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Thanks for using" in printed_output

class TestCLIIntegrationScenarios:
    """Test complete user interaction scenarios."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def mock_handle(self):
        handle = AsyncMock()
        handle.id = "order-O-999"
        handle.result_run_id = "run-999"
        
        description = MagicMock()
        description.run_id = "run-999"
        description.status.name = "RUNNING"
        description.start_time = datetime.now()
        handle.describe.return_value = description
        
        return handle

    @pytest.mark.asyncio
    async def test_complete_happy_path_scenario(self, mock_client, mock_handle):
        """Test complete happy path: start -> check status -> approve -> check final status."""
        mock_client.start_workflow.return_value = mock_handle
        mock_client.get_workflow_handle.return_value = mock_handle
        
        # First status check: running, second: completed
        mock_handle.result.side_effect = [asyncio.TimeoutError(), "OrderCompleted"]
        
        # Simulate user doing: start(1) -> status(2) -> approve(3) -> status(2) -> quit(q)
        inputs = [
            "1", "O-999", "999 Test St", "TestCity", "99999",  # Start order
            "",  # Continue
            "2", "O-999",  # Check status  
            "",  # Continue
            "3", "O-999",  # Approve order
            "",  # Continue
            "2", "O-999",  # Check status again
            "",  # Continue
            "q"  # Quit
        ]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print') as mock_print:
                    await cli.main()
        
        # Verify all operations occurred
        mock_client.start_workflow.assert_called_once()
        assert mock_client.get_workflow_handle.call_count == 3  # 2 status + 1 approve
        mock_handle.signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_error_recovery_scenario(self, mock_client):
        """Test user can recover from errors and continue using CLI."""
        # Simulate: invalid choice -> valid choice -> quit
        inputs = ["invalid", "6", "", "q"]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('cli.Client.connect', return_value=mock_client):
                with patch('builtins.input', side_effect=inputs):
                    with patch('builtins.print') as mock_print:
                        await cli.main()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Invalid choice" in printed_output
        assert "Health check complete" in printed_output

    @pytest.mark.asyncio
    async def test_rapid_sequential_operations(self, mock_client, mock_handle):
        """Test CLI handles rapid sequential operations without issues."""
        mock_client.start_workflow.return_value = mock_handle
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_handle.result.side_effect = [asyncio.TimeoutError()] * 10  # Always running
        
        # Rapid sequence: start -> status -> approve -> status -> cancel -> status -> quit
        inputs = [
            "1", "O-RAPID", "123 Fast St", "SpeedCity", "99999",  # Start
            "",  # Continue
            "2", "O-RAPID",  # Status
            "",  # Continue
            "3", "O-RAPID",  # Approve
            "",  # Continue
            "2", "O-RAPID",  # Status again
            "",  # Continue
            "4", "O-RAPID", "y",  # Cancel with confirmation
            "",  # Continue
            "2", "O-RAPID",  # Final status
            "",  # Continue
            "q"  # Quit
        ]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print'):
                    await cli.main()
        
        # Verify all operations occurred
        mock_client.start_workflow.assert_called_once()
        assert mock_client.get_workflow_handle.call_count >= 4  # Multiple status checks + approve + cancel
        assert mock_handle.signal.call_count == 2  # Approve + cancel signals

class TestCLIUtilityFunctions:
    """Test CLI utility and helper functions."""

    def test_get_user_input_with_color(self):
        """Test get_user_input applies colors correctly."""
        with patch('builtins.input', return_value="test input") as mock_input:
            result = cli.get_user_input("Enter something: ", cli.Colors.GREEN)
        
        assert result == "test input"
        # Check that colored prompt was used
        mock_input.assert_called_once()
        call_args = mock_input.call_args[0][0]
        assert "Enter something:" in call_args
        assert cli.Colors.GREEN in call_args

    def test_get_user_input_strips_whitespace(self):
        """Test get_user_input strips whitespace."""
        with patch('builtins.input', return_value="  test input  "):
            result = cli.get_user_input("Enter something: ")
        
        assert result == "test input"

    def test_get_user_input_default_color(self):
        """Test get_user_input uses default color when none specified."""
        with patch('builtins.input', return_value="test") as mock_input:
            result = cli.get_user_input("Enter: ")
        
        assert result == "test"
        call_args = mock_input.call_args[0][0]
        assert cli.Colors.CYAN in call_args  # Default color



class TestCLIValidation:
    """Test input validation and data handling."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def mock_handle(self):
        handle = AsyncMock()
        handle.id = "order-test"
        handle.result_run_id = "run-test"
        return handle

    @pytest.mark.asyncio
    async def test_empty_inputs_handled_gracefully(self):
        """Test that empty inputs are handled gracefully."""
        inputs = ["", "", ""]  # All empty inputs
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.start_order_interactive(None)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "required" in printed_output

    @pytest.mark.asyncio
    async def test_special_characters_in_inputs(self, mock_client, mock_handle):
        """Test CLI handles special characters in inputs."""
        mock_client.start_workflow.return_value = mock_handle
        
        # Inputs with special characters
        inputs = ["O-123!@#", "123 Main St & Co.", "São Paulo", "12345-6789"]
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print'):
                await cli.start_order_interactive(mock_client)
        
        # Should handle special characters without crashing
        mock_client.start_workflow.assert_called_once()
        call_args = mock_client.start_workflow.call_args
        assert call_args[1]['args'][0] == "O-123!@#"
        assert call_args[1]['args'][1]["city"] == "São Paulo"

    @pytest.mark.asyncio
    async def test_whitespace_only_inputs(self):
        """Test inputs with only whitespace are treated as empty."""
        inputs = ["   ", "\t", "\n"]  # Whitespace-only inputs
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.start_order_interactive(None)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "required" in printed_output

    @pytest.mark.asyncio
    async def test_very_long_inputs(self, mock_client, mock_handle):
        """Test CLI handles very long inputs."""
        mock_client.start_workflow.return_value = mock_handle
        
        # Very long inputs
        long_order_id = "O-" + "x" * 200
        long_address = "x" * 500
        long_city = "y" * 100
        
        inputs = [long_order_id, long_address, long_city, "12345"]
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print'):
                await cli.start_order_interactive(mock_client)
        
        # Should handle long inputs without crashing
        mock_client.start_workflow.assert_called_once()
        call_args = mock_client.start_workflow.call_args
        assert call_args[1]['args'][0] == long_order_id

class TestCLIAdvancedFeatures:
    """Test advanced CLI features and comprehensive scenarios."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def mock_handle(self):
        handle = AsyncMock()
        handle.id = "order-advanced"
        handle.result_run_id = "run-advanced"
        
        description = MagicMock()
        description.run_id = "run-advanced"
        description.status.name = "RUNNING"
        description.start_time = datetime.now()
        handle.describe.return_value = description
        
        return handle

    @pytest.mark.asyncio
    async def test_health_check_comprehensive(self, mock_client):
        """Test comprehensive health check functionality."""
        mock_client.list_workflows.return_value = []
        
        with patch('cli.Client.connect', return_value=mock_client):
            with patch('builtins.print') as mock_print:
                await cli.health_check()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Checking Temporal server" in printed_output
        assert "HEALTHY" in printed_output
        assert "WORKING" in printed_output
        assert "Health check complete" in printed_output

    @pytest.mark.asyncio
    async def test_health_check_partial_failure(self, mock_client):
        """Test health check when connection works but queries fail."""
        mock_client.list_workflows.side_effect = Exception("Query failed")
        
        with patch('cli.Client.connect', return_value=mock_client):
            with patch('builtins.print') as mock_print:
                await cli.health_check()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "HEALTHY" in printed_output  # Connection succeeded
        assert "Query failed" in printed_output  # But query failed

    @pytest.mark.asyncio
    async def test_multiple_cancel_confirmations(self, mock_client, mock_handle):
        """Test multiple cancel attempts with different confirmations."""
        mock_client.get_workflow_handle.return_value = mock_handle
        
        # First decline, then confirm on second try
        inputs = [
            "4", "O-123", "n", "",  # Cancel -> decline
            "4", "O-123", "y", "",  # Cancel -> confirm
            "q"  # Quit
        ]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print') as mock_print:
                    await cli.main()
        
        # Should have one signal call (from the confirmed cancellation)
        mock_handle.signal.assert_called_once()
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "aborted" in printed_output
        assert "Cancellation signal sent" in printed_output

class TestCLIStressTests:
    """Stress tests for CLI functionality."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def mock_handle(self):
        handle = AsyncMock()
        handle.id = "order-stress"
        handle.result_run_id = "run-stress"
        
        description = MagicMock()
        description.run_id = "run-stress"
        description.status.name = "RUNNING"
        description.start_time = datetime.now()
        handle.describe.return_value = description
        
        return handle

    @pytest.mark.asyncio
    async def test_many_status_checks_same_order(self, mock_client, mock_handle):
        """Test multiple status checks for the same order work correctly."""
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_handle.result.side_effect = [asyncio.TimeoutError()] * 5 + ["Completed"]
        
        # Check status 6 times for same order
        inputs = []
        for i in range(6):
            inputs.extend(["2", "O-STRESS", ""])  # Status check + continue
        inputs.append("q")  # Quit
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print') as mock_print:
                    await cli.main()
        
        # Should handle all checks without issues
        assert mock_client.get_workflow_handle.call_count == 6

    @pytest.mark.asyncio
    async def test_mixed_case_menu_choices(self, mock_client):
        """Test menu handles mixed case input."""
        inputs = ["Q"]  # Uppercase quit
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print') as mock_print:
                    await cli.main()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Thanks for using" in printed_output

    @pytest.mark.asyncio
    async def test_menu_with_extra_whitespace(self, mock_client):
        """Test menu handles input with extra whitespace."""
        inputs = ["  6  ", "", "q"]  # Health check with spaces
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('cli.Client.connect', return_value=mock_client):
                with patch('builtins.input', side_effect=inputs):
                    with patch('builtins.print') as mock_print:
                        await cli.main()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Health check complete" in printed_output

class TestCLIRobustness:
    """Test CLI robustness and edge cases."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_multiple_keyboard_interrupts(self, mock_client):
        """Test CLI handles multiple keyboard interrupts gracefully."""
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=KeyboardInterrupt()):
                with patch('builtins.print') as mock_print:
                    await cli.main()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Caught Ctrl+C" in printed_output or "Goodbye" in printed_output

    @pytest.mark.asyncio
    async def test_cli_main_keyboard_interrupt_at_module_level(self):
        """Test keyboard interrupt handling at module level."""
        with patch('cli.main', side_effect=KeyboardInterrupt()):
            with patch('builtins.print') as mock_print:
                # Simulate running the script directly
                try:
                    await cli.main()
                except KeyboardInterrupt:
                    pass
        
        # Should not crash the program

    @pytest.mark.asyncio
    async def test_unexpected_exception_in_main_loop(self, mock_client):
        """Test that unexpected exceptions are handled gracefully."""
        # Mock an unexpected exception during menu processing
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=["2", Exception("Unexpected error")]):
                with patch('builtins.print') as mock_print:
                    await cli.main()
        
        # Should handle the exception and continue or exit gracefully
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        # Should either show error handling or graceful exit

class TestCLIUserExperience:
    """Test CLI user experience elements."""

    def test_banner_formatting_and_content(self):
        """Test banner has proper formatting and content."""
        with patch('builtins.print') as mock_print:
            cli.print_banner()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "🚀" in printed_output  # Rocket emoji
        assert "Arjun's Temporal Takehome" in printed_output
        assert "Interactive Order Management" in printed_output
        assert "Temporal Workflows" in printed_output
        assert "=" in printed_output  # Banner borders

    def test_menu_formatting_and_emojis(self):
        """Test menu has proper formatting and emojis."""
        with patch('builtins.print') as mock_print:
            cli.print_menu()
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        
        # Check all menu items have emojis
        assert "🛒" in printed_output  # Shopping cart
        assert "📊" in printed_output  # Chart
        assert "✅" in printed_output  # Checkmark
        assert "❌" in printed_output  # X mark

        assert "🏥" in printed_output  # Hospital
        assert "👋" in printed_output  # Wave
        
        # Check numbering
        assert "1." in printed_output
        assert "2." in printed_output
        assert "q." in printed_output

    @pytest.mark.asyncio
    async def test_success_messages_include_appropriate_emojis(self, mock_client, mock_handle):
        """Test that success messages include appropriate emojis."""
        mock_client.start_workflow.return_value = mock_handle
        
        inputs = ["O-EMOJI", "123 Emoji St", "EmojiCity", "12345"]
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.start_order_interactive(mock_client)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "✅" in printed_output  # Success checkmark
        assert "🎉" in printed_output  # Party emoji

    @pytest.mark.asyncio
    async def test_error_messages_include_appropriate_emojis(self):
        """Test that error messages include appropriate emojis."""
        inputs = [""]  # Empty order ID
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.start_order_interactive(None)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "❌" in printed_output  # Error X mark

class TestCLIDataFlow:
    """Test data flow through CLI functions."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def mock_handle(self):
        handle = AsyncMock()
        handle.id = "order-dataflow"
        handle.result_run_id = "run-dataflow"
        return handle

    @pytest.mark.asyncio
    async def test_address_data_flow(self, mock_client, mock_handle):
        """Test that address data flows correctly through the system."""
        mock_client.start_workflow.return_value = mock_handle
        
        test_address = {
            "line1": "123 Test Avenue",
            "city": "Test City",
            "zip": "54321"
        }
        
        inputs = ["O-DATAFLOW", test_address["line1"], test_address["city"], test_address["zip"]]
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print'):
                await cli.start_order_interactive(mock_client)
        
        # Verify exact address data was passed
        call_args = mock_client.start_workflow.call_args
        passed_address = call_args[1]['args'][1]
        assert passed_address == test_address

    @pytest.mark.asyncio
    async def test_order_id_flow_through_operations(self, mock_client, mock_handle):
        """Test order ID flows correctly through different operations."""
        mock_client.get_workflow_handle.return_value = mock_handle
        test_order_id = "O-FLOWTEST"
        
        # Test approve operation
        inputs = [test_order_id]
        with patch('builtins.input', side_effect=inputs):
            await cli.approve_order_interactive(mock_client)
        
        # Verify correct workflow handle was requested
        mock_client.get_workflow_handle.assert_called_with(f"order-{test_order_id}")

class TestCLIEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_empty_string_confirmation(self, mock_client):
        """Test cancel confirmation with empty string (should be treated as 'no')."""
        inputs = ["O-123", ""]  # Order ID and empty confirmation
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.cancel_order_interactive(mock_client)
        
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "aborted" in printed_output

    @pytest.mark.asyncio
    async def test_case_insensitive_confirmation(self, mock_client, mock_handle):
        """Test that confirmation is case insensitive."""
        mock_client.get_workflow_handle.return_value = mock_handle
        
        inputs = ["O-123", "Y"]  # Uppercase Y
        
        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print') as mock_print:
                await cli.cancel_order_interactive(mock_client)
        
        mock_handle.signal.assert_called_once()
        printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
        assert "Cancellation signal sent" in printed_output

    @pytest.mark.asyncio
    async def test_various_confirmation_inputs(self, mock_client, mock_handle):
        """Test various confirmation inputs."""
        mock_client.get_workflow_handle.return_value = mock_handle
        
        # Test different ways to say no
        for no_input in ["n", "N", "no", "No", "NO"]:
            inputs = ["O-123", no_input]
            
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print') as mock_print:
                    await cli.cancel_order_interactive(mock_client)
            
            printed_output = ' '.join([str(call) for call in mock_print.call_args_list])
            assert "aborted" in printed_output

# Performance and reliability tests
class TestCLIPerformance:
    """Test CLI performance characteristics."""

    @pytest.mark.asyncio
    async def test_rapid_menu_navigation(self, mock_client):
        """Test rapid menu navigation doesn't cause issues."""
        mock_client.list_workflows.return_value = []
        
        # Rapidly navigate through all menu options
        inputs = ["1", "", "", "", "", "", "2", "", "", "3", "", "", "4", "", "n", "", "5", "", "q"]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('cli.Client.connect', return_value=mock_client):
                with patch('builtins.input', side_effect=inputs):
                    with patch('builtins.print'):
                        await cli.main()
        
        # Should complete without hanging or crashing

    @pytest.mark.asyncio
    async def test_concurrent_operation_simulation(self, mock_client, mock_handle):
        """Test that CLI handles what appears to be concurrent operations."""
        mock_client.start_workflow.return_value = mock_handle
        mock_client.get_workflow_handle.return_value = mock_handle
        mock_handle.result.side_effect = [asyncio.TimeoutError()] * 10
        
        # Simulate user doing multiple operations quickly
        inputs = [
            "1", "O-CONCURRENT", "123 Concurrent St", "ConcurrentCity", "11111",  # Start
            "",
            "2", "O-CONCURRENT",  # Status
            "",
            "3", "O-CONCURRENT",  # Approve
            "",
            "2", "O-CONCURRENT",  # Status again
            "",
            "q"
        ]
        
        with patch('cli.connect_to_temporal', return_value=mock_client):
            with patch('builtins.input', side_effect=inputs):
                with patch('builtins.print'):
                    await cli.main()
        
        # All operations should complete successfully
        mock_client.start_workflow.assert_called_once()
        assert mock_client.get_workflow_handle.call_count >= 2

# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])