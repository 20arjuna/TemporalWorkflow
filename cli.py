#!/usr/bin/env python3
"""
🚀 Arjun's Temporal Takehome - Interactive Order Management CLI
A beautiful, interactive CLI for managing orders via Temporal workflows.
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from temporalio.client import Client

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from workflows.order_workflow import OrderWorkflow
from db.connection import startup_db, shutdown_db
from db.queries import OrderQueries, PaymentQueries, EventQueries, RetryQueries, ObservabilityQueries

# Color codes for beautiful output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_banner():
    """Print the welcome banner."""
    print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}🚀 Welcome to Arjun's Temporal Demo 🚀{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}Interactive Order Management System{Colors.END}")
    print(f"{Colors.YELLOW}Powered by Temporal Workflows ⚡{Colors.END}\n")

def print_menu():
    """Print the main menu."""
    print(f"{Colors.BOLD}📋 Main Menu:{Colors.END}")
    print(f"{Colors.GREEN}  1.{Colors.END} 🛒 Start a new order")
    print(f"{Colors.GREEN}  2.{Colors.END} 📊 Check order status") 
    print(f"{Colors.GREEN}  3.{Colors.END} ✅ Approve an order")
    print(f"{Colors.GREEN}  4.{Colors.END} 📍 Update order address")
    print(f"{Colors.GREEN}  5.{Colors.END} ❌ Cancel an order")
    print(f"{Colors.CYAN}  6.{Colors.END} 🔍 View audit logs")
    print(f"{Colors.RED}  q.{Colors.END} 👋 Quit")
    print()

def get_user_input(prompt: str, color: str = Colors.CYAN) -> str:
    """Get user input with colored prompt."""
    return input(f"{color}{prompt}{Colors.END}").strip()

def print_success(message: str):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message: str):
    """Print error message."""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_info(message: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def print_warning(message: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def get_order_step(workflow_status: str, result: str = None) -> tuple:
    """Get the current step and color for an order."""
    # Handle completed workflows first
    if workflow_status == "COMPLETED" or result:
        if result:
            if "Cancelled" in result or "AutoCancelled" in result:
                return "Cancelled", Colors.RED
            elif "Failed" in result:
                return "Failed", Colors.RED
            else:
                return "Completed", Colors.GREEN
        else:
            return "Completed", Colors.GREEN
    
    # Running orders - map to current step with more granular stages
    if workflow_status == "RUNNING":
        # For now, we'll show "Pending Approval" but this could be enhanced
        # to detect the actual current stage by checking workflow history
        return "Pending Approval", Colors.YELLOW
    else:
        # Any other running state or error
        if "ERROR" in workflow_status or "FAILED" in workflow_status:
            return workflow_status, Colors.RED
        else:
            return workflow_status, Colors.YELLOW

async def print_pizza_tracker(order_id: str, current_stage: str, result: str = None):
    """Print an enhanced Domino's-style pizza tracker with database insights."""
    print(f"\n{Colors.BOLD}🍕 Enhanced Order Tracker - {order_id}{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}")
    
    try:
        # Initialize database and get comprehensive order info
        await startup_db()
        health_report = await ObservabilityQueries.get_order_health_report(order_id)
        
        if "error" in health_report:
            print(f"{Colors.RED}❌ {health_report['error']}{Colors.END}")
            return
        
        order = health_report["order"]
        health_metrics = health_report["health_metrics"]
        timeline = health_report["timeline"]
        
        # Map database states to display stages
        db_state = order["state"]
        stage_map = {
            "received": "received",
            "validating": "validating", 
            "validated": "validated",
            "charging_payment": "charging_payment",
            "payment_charged": "payment_charged",
            "preparing_package": "preparing_package",
            "package_prepared": "package_prepared",
            "dispatching_carrier": "dispatching_carrier",
            "shipped": "shipped",
            "validation_failed": "validation_failed",
            "payment_failed": "payment_failed",
            "package_preparation_failed": "package_preparation_failed",
            "carrier_dispatch_failed": "carrier_dispatch_failed"
        }
        
        # Enhanced stages with more granular tracking
        stages = [
            ("📝", "Order Received", "received"),
            ("🔍", "Validating", "validating"),
            ("✅", "Validated", "validated"), 
            ("⏳", "Pending Approval", "pending_approval"),
            ("💳", "Charging Payment", "charging_payment"),
            ("💰", "Payment Complete", "payment_charged"),
            ("📦", "Preparing Package", "preparing_package"),
            ("📋", "Package Ready", "package_prepared"),
            ("🚚", "Dispatching Carrier", "dispatching_carrier"),
            ("🎉", "Shipped!", "shipped")
        ]
        
        current_stage_key = stage_map.get(db_state, db_state)
        
        # Handle failure states
        if "failed" in current_stage_key:
            print(f"\n{Colors.RED}❌ Order Failed{Colors.END}")
            print(f"   {Colors.RED}State: {db_state}{Colors.END}")
            print(f"   {Colors.RED}Success Rate: {health_metrics['success_rate']}%{Colors.END}")
            print(f"   {Colors.RED}Failed Attempts: {health_metrics['failed_attempts']}/{health_metrics['total_attempts']}{Colors.END}")
            await show_failure_details(timeline)
            return
        
        if current_stage_key == "cancelled":
            print(f"\n{Colors.RED}❌ Order Cancelled{Colors.END}")
            print(f"   {Colors.RED}Status: {current_stage}{Colors.END}")
            return
        
        # Find current stage index
        current_idx = 0
        for i, (_, _, key) in enumerate(stages):
            if key == current_stage_key:
                current_idx = i
                break
        
        # If shipped, show all stages as done
        if current_stage_key == "shipped":
            current_idx = len(stages) - 1
        
        print()
        
        # Print enhanced progress bar with timing info
        events = timeline["events"]
        for i, (emoji, name, key) in enumerate(stages):
            # Find the event for this stage
            stage_event = next((e for e in events if key in e['event_type']), None)
            
            if i <= current_idx:
                # Completed or current stage
                if i == current_idx and current_stage_key != "shipped":
                    # Current stage (in progress)
                    print(f"{Colors.YELLOW}{emoji} {name} {Colors.BOLD}← YOU ARE HERE{Colors.END}")
                else:
                    # Completed stage
                    timestamp = ""
                    if stage_event:
                        ts = stage_event['ts']
                        timestamp = f" ({ts.strftime('%H:%M:%S')})"
                    print(f"{Colors.GREEN}{emoji} {name} ✓{timestamp}{Colors.END}")
            else:
                # Future stage
                print(f"{Colors.CYAN}{emoji} {name}{Colors.END}")
        
        print()
        
        # Show enhanced metrics
        await show_order_metrics(health_metrics, timeline)
        
        # Show result if completed
        if result and current_stage_key == "shipped":
            print(f"{Colors.GREEN}🎉 Final Result: {result}{Colors.END}")
        
        print(f"{Colors.CYAN}{'='*60}{Colors.END}")
        
    except Exception as e:
        print(f"{Colors.RED}❌ Error loading order details: {e}{Colors.END}")
        # Fallback to original simple tracker
        print_simple_pizza_tracker(order_id, current_stage, result)

def print_simple_pizza_tracker(order_id: str, current_stage: str, result: str = None):
    """Fallback simple pizza tracker (original version)."""
    print(f"\n{Colors.BOLD}🍕 Order Tracker - {order_id}{Colors.END}")
    print(f"{Colors.CYAN}{'='*50}{Colors.END}")
    
    # Define the stages (simplified)
    stages = [
        ("📝", "Order Received", "received"),
        ("✅", "Validated", "validated"), 
        ("⏳", "Pending Approval", "pending_approval"),
        ("💳", "Charging Payment", "charging_payment"),
        ("📦", "Preparing Package", "preparing"),
        ("🚚", "Out for Delivery", "shipping"),
        ("🎉", "Delivered!", "completed")
    ]
    
    # Simple stage mapping
    stage_map = {
        "RUNNING": "pending_approval",
        "OrderCompleted": "completed",
        "OrderShipped": "completed", 
        "Cancelled": "cancelled",
        "AutoCancelled": "cancelled",
        "PaymentFailed": "payment_failed",
        "ValidationFailed": "validation_failed"
    }
    
    current_stage_key = stage_map.get(current_stage, "pending_approval")
    
    if current_stage_key == "cancelled":
        print(f"\n{Colors.RED}❌ Order Cancelled{Colors.END}")
        return
    
    if current_stage_key in ["payment_failed", "validation_failed"]:
        print(f"\n{Colors.RED}❌ Order Failed{Colors.END}")
        return
    
    # Find current stage index
    current_idx = 0
    for i, (_, _, key) in enumerate(stages):
        if key == current_stage_key:
            current_idx = i
            break
    
    if current_stage_key == "completed":
        current_idx = len(stages) - 1
    
    print()
    
    # Print simple progress bar
    for i, (emoji, name, key) in enumerate(stages):
        if i <= current_idx:
            if i == current_idx and current_stage_key != "completed":
                print(f"{Colors.YELLOW}{emoji} {name} {Colors.BOLD}← YOU ARE HERE{Colors.END}")
            else:
                print(f"{Colors.GREEN}{emoji} {name} ✓{Colors.END}")
        else:
            print(f"{Colors.CYAN}{emoji} {name}{Colors.END}")
    
    print()
    if result and current_stage_key == "completed":
        print(f"{Colors.GREEN}🎉 Final Result: {result}{Colors.END}")
    
    print(f"{Colors.CYAN}{'='*50}{Colors.END}")

async def show_order_metrics(health_metrics: dict, timeline: dict):
    """Show enhanced order metrics and insights."""
    print(f"{Colors.BOLD}📊 Order Health Metrics:{Colors.END}")
    
    # Success rate with color coding
    success_rate = health_metrics["success_rate"]
    if success_rate >= 90:
        rate_color = Colors.GREEN
    elif success_rate >= 70:
        rate_color = Colors.YELLOW
    else:
        rate_color = Colors.RED
    
    print(f"   {rate_color}Success Rate: {success_rate}%{Colors.END}")
    print(f"   Total Attempts: {health_metrics['total_attempts']}")
    print(f"   Failed Attempts: {health_metrics['failed_attempts']}")
    print(f"   Avg Execution: {health_metrics['avg_execution_time_ms']}ms")
    
    # Payment info
    payments = timeline["payments"]
    if payments:
        payment = payments[0]  # Most recent payment
        payment_color = Colors.GREEN if payment["status"] == "charged" else Colors.RED
        print(f"   {payment_color}Payment: {payment['status']} - ${payment['amount']}{Colors.END}")
        if health_metrics['payment_retries'] > 0:
            print(f"   {Colors.YELLOW}Payment Retries: {health_metrics['payment_retries']}{Colors.END}")
    
    print()

async def show_failure_details(timeline: dict):
    """Show detailed failure information."""
    print(f"{Colors.BOLD}🔍 Failure Analysis:{Colors.END}")
    
    # Show recent events leading to failure
    events = timeline["events"][-5:]  # Last 5 events
    print(f"   {Colors.YELLOW}Recent Events:{Colors.END}")
    for event in events:
        event_color = Colors.RED if "failed" in event['event_type'] else Colors.CYAN
        print(f"      {event_color}- {event['event_type']} at {event['ts'].strftime('%H:%M:%S')}{Colors.END}")
    
    # Show payment attempts if any
    payments = timeline["payments"]
    if payments:
        print(f"   {Colors.YELLOW}Payment Attempts:{Colors.END}")
        for payment in payments:
            payment_color = Colors.GREEN if payment["status"] == "charged" else Colors.RED
            print(f"      {payment_color}- {payment['payment_id']}: {payment['status']}{Colors.END}")
    
    print()

async def view_audit_logs_interactive(client):
    """Show recent order events directly."""
    try:
        await startup_db()
        await show_recent_events()
    except Exception as e:
        print_error(f"Failed to load audit logs: {e}")

async def show_recent_events():
    """Show recent events across all orders."""
    print(f"\n{Colors.BOLD}📋 Recent Order Events{Colors.END}")
    print("-" * 30)
    
    events = await EventQueries.get_recent_events(20)
    if not events:
        print(f"{Colors.CYAN}No events found{Colors.END}")
        return
    
    for event in events:
        event_color = Colors.RED if "failed" in event['event_type'] else Colors.GREEN if "completed" in event['event_type'] or "charged" in event['event_type'] else Colors.CYAN
        print(f"{event_color}{event['ts'].strftime('%H:%M:%S')} - {event['order_id']} - {event['event_type']}{Colors.END}")

async def show_recent_failures():
    """Show recent failed activities."""
    print(f"\n{Colors.BOLD}⚠️  Recent Failures (24h){Colors.END}")
    print("-" * 30)
    
    failures = await RetryQueries.get_failed_activities(24)
    if not failures:
        print(f"{Colors.GREEN}No failures in the last 24 hours! 🎉{Colors.END}")
        return
    
    for failure in failures:
        print(f"{Colors.RED}❌ {failure['activity_name']} - Order: {failure['order_id']}{Colors.END}")
        print(f"   Attempt: {failure['attempt_number']}")
        print(f"   Error: {failure['error_message'][:80]}...")
        print(f"   Time: {failure['started_at'].strftime('%Y-%m-%d %H:%M:%S')}")
        print()

async def show_retry_summaries():
    """Show retry summaries for recent orders."""
    print(f"\n{Colors.BOLD}🔄 Retry Summaries{Colors.END}")
    print("-" * 30)
    
    summaries = await RetryQueries.get_all_retry_summaries(10)
    if not summaries:
        print(f"{Colors.CYAN}No retry data available{Colors.END}")
        return
    
    for summary in summaries:
        retry_color = Colors.GREEN if summary['failed_attempts'] == 0 else Colors.YELLOW if summary['failed_attempts'] <= 2 else Colors.RED
        print(f"{retry_color}{summary['order_id']} - {summary['current_state']}{Colors.END}")
        print(f"   Total Attempts: {summary['total_activity_attempts']}")
        print(f"   Failed: {summary['failed_attempts']}")
        print(f"   Success: {summary['successful_attempts']}")
        if summary['max_payment_retries'] and summary['max_payment_retries'] > 0:
            print(f"   Payment Retries: {summary['max_payment_retries']}")
        print()

async def show_activity_performance():
    """Show detailed activity performance metrics."""
    print(f"\n{Colors.BOLD}📊 Activity Performance Analysis{Colors.END}")
    print("-" * 40)
    
    performance = await RetryQueries.get_activity_performance()
    if not performance:
        print(f"{Colors.CYAN}No activity performance data available{Colors.END}")
        return
    
    for activity in performance:
        success_rate = (activity['successful_attempts'] / activity['total_attempts']) * 100 if activity['total_attempts'] > 0 else 0
        
        # Color code based on performance
        if success_rate >= 95:
            perf_color = Colors.GREEN
            perf_status = "EXCELLENT"
        elif success_rate >= 85:
            perf_color = Colors.YELLOW
            perf_status = "GOOD"
        else:
            perf_color = Colors.RED
            perf_status = "POOR"
        
        print(f"{perf_color}{activity['activity_name']} - {perf_status}{Colors.END}")
        print(f"   Success Rate: {success_rate:.1f}%")
        print(f"   Attempts: {activity['successful_attempts']}/{activity['total_attempts']}")
        print(f"   Failures: {activity['failed_attempts']}")
        print(f"   Timeouts: {activity['timeout_attempts']}")
        print(f"   Avg Time: {activity['avg_execution_time_ms']}ms")
        print(f"   Max Time: {activity['max_execution_time_ms']}ms")
        print()

async def show_order_deep_dive(client):
    """Show deep dive analysis for a specific order."""
    print(f"\n{Colors.BOLD}🔍 Order Deep Dive{Colors.END}")
    print("-" * 30)
    
    order_id = get_user_input("Enter Order ID to analyze: ")
    if not order_id:
        print_error("Order ID is required!")
        return
    
    try:
        health_report = await ObservabilityQueries.get_order_health_report(order_id)
        
        if "error" in health_report:
            print_error(health_report["error"])
            return
        
        order = health_report["order"]
        health_metrics = health_report["health_metrics"]
        timeline = health_report["timeline"]
        
        # Order summary
        print(f"{Colors.BOLD}📦 Order Summary:{Colors.END}")
        print(f"   ID: {order['id']}")
        print(f"   State: {order['state']}")
        print(f"   Created: {order['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Address: {order['address_json']['line1']}, {order['address_json']['city']}")
        
        # Health metrics
        print(f"\n{Colors.BOLD}📊 Health Metrics:{Colors.END}")
        success_color = Colors.GREEN if health_metrics['success_rate'] >= 90 else Colors.YELLOW if health_metrics['success_rate'] >= 70 else Colors.RED
        print(f"   {success_color}Success Rate: {health_metrics['success_rate']}%{Colors.END}")
        print(f"   Total Attempts: {health_metrics['total_attempts']}")
        print(f"   Failed Attempts: {health_metrics['failed_attempts']}")
        print(f"   Avg Execution: {health_metrics['avg_execution_time_ms']}ms")
        
        # Payment details
        payments = timeline["payments"]
        if payments:
            print(f"\n{Colors.BOLD}💳 Payment History:{Colors.END}")
            for payment in payments:
                payment_color = Colors.GREEN if payment["status"] == "charged" else Colors.RED
                print(f"   {payment_color}{payment['payment_id']}: {payment['status']} - ${payment['amount']}{Colors.END}")
                print(f"      Created: {payment['created_at'].strftime('%H:%M:%S')}")
        
        # Event timeline
        events = timeline["events"]
        print(f"\n{Colors.BOLD}📝 Complete Event Timeline ({len(events)} events):{Colors.END}")
        for i, event in enumerate(events):
            event_color = Colors.RED if "failed" in event['event_type'] else Colors.GREEN if "completed" in event['event_type'] or "charged" in event['event_type'] else Colors.CYAN
            print(f"   {i+1:2d}. {event_color}{event['event_type']}{Colors.END}")
            print(f"       {event['ts'].strftime('%Y-%m-%d %H:%M:%S')}")
            if event.get('payload_json'):
                # Show key payload info
                payload = event['payload_json']
                if isinstance(payload, dict):
                    if 'error' in payload:
                        print(f"       {Colors.RED}Error: {payload['error'][:50]}...{Colors.END}")
                    elif 'amount' in payload:
                        print(f"       Amount: ${payload['amount']}")
                    elif 'source' in payload:
                        print(f"       Source: {payload['source']}")
        
        # Activity attempts (if any)
        attempts = timeline.get("attempts", [])
        if attempts:
            print(f"\n{Colors.BOLD}🔄 Activity Attempts:{Colors.END}")
            for attempt in attempts:
                attempt_color = Colors.GREEN if attempt["status"] == "completed" else Colors.RED
                print(f"   {attempt_color}{attempt['activity_name']} (Attempt {attempt['attempt_number']}): {attempt['status']}{Colors.END}")
                if attempt['execution_time_ms']:
                    print(f"      Execution Time: {attempt['execution_time_ms']}ms")
                if attempt['error_message']:
                    print(f"      Error: {attempt['error_message'][:60]}...")
        
    except Exception as e:
        print_error(f"Failed to load order deep dive: {e}")

async def connect_to_temporal():
    """Connect to Temporal server with retry logic."""
    print_info("Connecting to Temporal server...")
    try:
        client = await Client.connect("localhost:7233")
        print_success("Connected to Temporal! 🎉")
        return client
    except Exception as e:
        print_error(f"Failed to connect to Temporal: {e}")
        print_warning("Make sure your Temporal server is running:")
        print("   docker compose up -d")
        return None

async def start_order_interactive(client):
    """Interactive order creation."""
    print(f"\n{Colors.BOLD}🛒 Starting New Order{Colors.END}")
    print("-" * 30)
    
    order_id = get_user_input("Enter Order ID (e.g., O-123): ")
    if not order_id:
        print_error("Order ID is required!")
        return
    
    print(f"\n{Colors.BOLD}📍 Shipping Address:{Colors.END}")
    line1 = get_user_input("Street Address: ")
    city = get_user_input("City: ")
    zip_code = get_user_input("ZIP Code: ")
    
    if not all([line1, city, zip_code]):
        print_error("All address fields are required!")
        return
    
    address = {"line1": line1, "city": city, "zip": zip_code}
    
    print(f"\n{Colors.YELLOW}🔄 Starting workflow...{Colors.END}")
    
    try:
        handle = await client.start_workflow(
            OrderWorkflow.run,
            args=[order_id, address],
            id=f"order-{order_id}",
            task_queue="orders-tq",
        )
        
        print_success(f"Order {order_id} started successfully!")
        print(f"   {Colors.BLUE}Workflow ID:{Colors.END} {handle.id}")
        print(f"   {Colors.BLUE}Run ID:{Colors.END} {handle.result_run_id}")
        print_warning("Remember: You have 30 seconds to approve this order!")
        
    except Exception as e:
        print_error(f"Failed to start order: {e}")

async def check_status_interactive(client):
    """Interactive status checking with expandable order details."""
    print(f"\n{Colors.BOLD}📊 Order Status Dashboard{Colors.END}")
    print("-" * 60)
    
    print(f"\n{Colors.YELLOW}🔍 Fetching all orders...{Colors.END}")
    
    try:
        # Get all workflows with our naming pattern
        workflows_iter = client.list_workflows("WorkflowType = 'OrderWorkflow'")
        
        workflows = []
        async for workflow in workflows_iter:
            workflows.append(workflow)
        
        if not workflows:
            print_warning("No orders found!")
            print_info("Start an order first using option 1")
            return
        
        # Sort workflows by start time (most recent last) and take only the 3 most recent
        workflows.sort(key=lambda w: w.start_time if w.start_time else datetime.min)
        recent_workflows = workflows[-3:]  # Last 3 (most recent)
        
        # Collect order data for display
        order_data = []
        
        # Initialize database for enhanced status info
        await startup_db()
        
        # Display orders in a nice table with current steps
        print(f"\n{Colors.BOLD}📋 Recent Orders (Last 3) - Enhanced with DB Info:{Colors.END}")
        print(f"{Colors.CYAN}{'#':<3} {'Order ID':<15} {'Current Step':<25} {'DB State':<15} {'Retries':<8} {'Started':<12}{Colors.END}")
        print(f"{Colors.CYAN}{'-'*3} {'-'*15} {'-'*25} {'-'*15} {'-'*8} {'-'*12}{Colors.END}")
        
        for i, workflow in enumerate(recent_workflows, 1):
            order_id = workflow.id.replace("order-", "")
            
            try:
                handle = client.get_workflow_handle(workflow.id)
                
                # Get Temporal workflow status
                try:
                    result = await handle.result(timeout=0.1)
                    # If we got a result, it's completed
                    step, color = get_order_step("COMPLETED", result)
                    workflow_status = "COMPLETED"
                except:
                    # Still running
                    description = await handle.describe()
                    step, color = get_order_step(description.status.name, None)
                    result = None
                    workflow_status = description.status.name
                
                # Get enhanced database state and retry count
                db_state = "N/A"
                retry_count = 0
                try:
                    db_order = await OrderQueries.get_order(order_id)
                    if db_order:
                        db_state = db_order["state"]
                        # Use database state for more accurate step if available
                        if db_state in ["received", "validating", "validated", "charging_payment", "payment_charged", 
                                       "preparing_package", "package_prepared", "dispatching_carrier", "shipped"]:
                            step = db_state.replace("_", " ").title()
                            if db_state == "shipped":
                                color = Colors.GREEN
                            elif "failed" in db_state:
                                color = Colors.RED
                            else:
                                color = Colors.YELLOW
                    
                    # Get retry count from failed events (more accurate than activity_attempts)
                    events = await EventQueries.get_order_events(order_id)
                    failed_events = [e for e in events if "failed" in e["event_type"]]
                    retry_count = len(failed_events)
                except:
                    pass  # Fall back to Temporal status
                
                start_time = workflow.start_time.strftime("%H:%M:%S") if workflow.start_time else "Unknown"
                
                # Color retry count based on severity
                retry_color = Colors.GREEN if retry_count == 0 else Colors.YELLOW if retry_count < 5 else Colors.RED
                
                print(f"{i:<3} {order_id:<15} {color}{step:<25}{Colors.END} {db_state:<15} {retry_color}{retry_count:<8}{Colors.END} {start_time:<12}")
                
                # Store data for selection
                order_data.append({
                    "order_id": order_id,
                    "workflow_id": workflow.id,
                    "status": workflow_status,
                    "result": result,
                    "start_time": start_time
                })
                
            except Exception as e:
                print(f"{i:<3} {order_id:<15} {Colors.RED}ERROR{Colors.END}            Unknown   {Colors.RED}?{Colors.END}        Unknown")
                order_data.append({
                    "order_id": order_id,
                    "workflow_id": workflow.id,
                    "status": "ERROR",
                    "result": None,
                    "start_time": "Unknown"
                })
        
        print(f"\n{Colors.GREEN}Select an order number to see detailed progress tracker{Colors.END}")
        print(f"{Colors.RED}  0.{Colors.END} Back to menu")
        print()
        
        # Get user choice
        choice = get_user_input(f"Select order to expand (1-{len(order_data)}, 0 to go back): ")
        
        if choice == "0" or not choice:
            print_info("Returning to main menu")
            return
        
        try:
            choice_idx = int(choice) - 1
            if choice_idx < 0 or choice_idx >= len(order_data):
                print_error("Invalid selection!")
                return
        except ValueError:
            print_error("Please enter a valid number!")
            return
        
        # Show enhanced pizza tracker for selected order
        selected_order = order_data[choice_idx]
        await print_pizza_tracker(
            selected_order["order_id"], 
            selected_order["status"], 
            selected_order["result"]
        )
        
    except Exception as e:
        print_error(f"Failed to fetch orders: {e}")
        print_info("Make sure your Temporal server is running and accessible")

async def update_address_interactive(client):
    """Interactive address update with order selection."""
    print(f"\n{Colors.BOLD}📍 Update Order Address{Colors.END}")
    print("-" * 40)
    
    print(f"\n{Colors.YELLOW}🔍 Finding orders that can be updated...{Colors.END}")
    
    try:
        # Get all running workflows (only pending orders can have address updated)
        workflows_iter = client.list_workflows("WorkflowType = 'OrderWorkflow' AND ExecutionStatus = 'Running'")
        
        workflows = []
        async for workflow in workflows_iter:
            workflows.append(workflow)
        
        updatable_orders = []
        for workflow in workflows:
            try:
                handle = client.get_workflow_handle(workflow.id)
                # Quick check if still running (not completed)
                try:
                    await handle.result(timeout=0.1)
                    # If we get here, it's completed, skip it
                    continue
                except:
                    # Still running, can potentially update address
                    order_id = workflow.id.replace("order-", "")
                    start_time = workflow.start_time.strftime("%H:%M:%S") if workflow.start_time else "Unknown"
                    updatable_orders.append({
                        "order_id": order_id,
                        "workflow_id": workflow.id,
                        "start_time": start_time
                    })
            except:
                continue
        
        if not updatable_orders:
            print_warning("No orders available for address updates!")
            print_info("Only pending orders can have their address changed")
            return
        
        # Display updatable orders
        print(f"\n{Colors.BOLD}📋 Orders Available for Address Update:{Colors.END}")
        for i, order in enumerate(updatable_orders, 1):
            print(f"{Colors.GREEN}  {i}.{Colors.END} {order['order_id']} (started at {order['start_time']})")
        
        print(f"{Colors.RED}  0.{Colors.END} Back to menu")
        print()
        
        # Get user choice
        choice = get_user_input(f"Select order to update address (1-{len(updatable_orders)}, 0 to go back): ")
        
        if choice == "0" or not choice:
            print_info("Returning to main menu")
            return
        
        try:
            choice_idx = int(choice) - 1
            if choice_idx < 0 or choice_idx >= len(updatable_orders):
                print_error("Invalid selection!")
                return
        except ValueError:
            print_error("Please enter a valid number!")
            return
        
        selected_order = updatable_orders[choice_idx]
        order_id = selected_order["order_id"]
        
        # Get new address
        print(f"\n{Colors.BOLD}📍 New Shipping Address for {order_id}:{Colors.END}")
        line1 = get_user_input("Street Address: ")
        city = get_user_input("City: ")
        zip_code = get_user_input("ZIP Code: ")
        
        if not all([line1, city, zip_code]):
            print_error("All address fields are required!")
            return
        
        new_address = {"line1": line1, "city": city, "zip": zip_code}
        
        # Confirm update
        print(f"\n{Colors.YELLOW}📍 New Address:{Colors.END}")
        print(f"   {line1}")
        print(f"   {city}, {zip_code}")
        
        confirm = get_user_input(f"\nUpdate address for order {order_id}? (y/N): ", Colors.YELLOW)
        if confirm.lower() != 'y':
            print_info("Address update cancelled")
            return
        
        # Send address update signal
        handle = client.get_workflow_handle(selected_order["workflow_id"])
        
        print(f"\n{Colors.YELLOW}📤 Sending address update signal...{Colors.END}")
        await handle.signal(OrderWorkflow.update_address, new_address)
        
        print_success(f"Address updated for order {order_id}! 📍✨")
        print_info("The workflow will use the new address for shipping")
        
    except Exception as e:
        print_error(f"Failed to update address: {e}")

async def approve_order_interactive(client):
    """Interactive order approval with order selection."""
    print(f"\n{Colors.BOLD}✅ Approve Order{Colors.END}")
    print("-" * 40)
    
    print(f"\n{Colors.YELLOW}🔍 Finding pending orders...{Colors.END}")
    
    try:
        # Get all running workflows
        workflows_iter = client.list_workflows("WorkflowType = 'OrderWorkflow' AND ExecutionStatus = 'Running'")
        
        workflows = []
        async for workflow in workflows_iter:
            workflows.append(workflow)
        
        pending_orders = []
        for workflow in workflows:
            try:
                handle = client.get_workflow_handle(workflow.id)
                # Quick check if still running (not completed)
                try:
                    await handle.result(timeout=0.1)
                    # If we get here, it's completed, skip it
                    continue
                except:
                    # Still running, add to pending list
                    order_id = workflow.id.replace("order-", "")
                    start_time = workflow.start_time.strftime("%H:%M:%S") if workflow.start_time else "Unknown"
                    pending_orders.append({
                        "order_id": order_id,
                        "workflow_id": workflow.id,
                        "start_time": start_time
                    })
            except:
                continue
        
        if not pending_orders:
            print_warning("No pending orders found!")
            print_info("All orders are either completed or cancelled")
            return
        
        # Display pending orders
        print(f"\n{Colors.BOLD}📋 Pending Orders:{Colors.END}")
        for i, order in enumerate(pending_orders, 1):
            print(f"{Colors.GREEN}  {i}.{Colors.END} {order['order_id']} (started at {order['start_time']})")
        
        print(f"{Colors.RED}  0.{Colors.END} Cancel")
        print()
        
        # Get user choice
        choice = get_user_input(f"Select order to approve (1-{len(pending_orders)}, 0 to cancel): ")
        
        if choice == "0" or not choice:
            print_info("Approval cancelled")
            return
        
        try:
            choice_idx = int(choice) - 1
            if choice_idx < 0 or choice_idx >= len(pending_orders):
                print_error("Invalid selection!")
                return
        except ValueError:
            print_error("Please enter a valid number!")
            return
        
        selected_order = pending_orders[choice_idx]
        order_id = selected_order["order_id"]
        
        # Confirm approval
        confirm = get_user_input(f"Approve order {order_id}? (y/N): ", Colors.YELLOW)
        if confirm.lower() != 'y':
            print_info("Approval cancelled")
            return
        
        # Send approval signal
        handle = client.get_workflow_handle(selected_order["workflow_id"])
        
        print(f"\n{Colors.YELLOW}📤 Sending approval signal...{Colors.END}")
        await handle.signal(OrderWorkflow.approve)
        
        print_success(f"Approval signal sent to order {order_id}! ✨")
        print_info("The workflow will continue processing...")
        
    except Exception as e:
        print_error(f"Failed to approve order: {e}")

async def cancel_order_interactive(client):
    """Interactive order cancellation with order selection."""
    print(f"\n{Colors.BOLD}❌ Cancel Order{Colors.END}")
    print("-" * 40)
    
    print(f"\n{Colors.YELLOW}🔍 Finding active orders...{Colors.END}")
    
    try:
        # Get all running workflows
        workflows_iter = client.list_workflows("WorkflowType = 'OrderWorkflow' AND ExecutionStatus = 'Running'")
        
        workflows = []
        async for workflow in workflows_iter:
            workflows.append(workflow)
        
        active_orders = []
        for workflow in workflows:
            try:
                handle = client.get_workflow_handle(workflow.id)
                # Quick check if still running (not completed)
                try:
                    await handle.result(timeout=0.1)
                    # If we get here, it's completed, skip it
                    continue
                except:
                    # Still running, add to active list
                    order_id = workflow.id.replace("order-", "")
                    start_time = workflow.start_time.strftime("%H:%M:%S") if workflow.start_time else "Unknown"
                    active_orders.append({
                        "order_id": order_id,
                        "workflow_id": workflow.id,
                        "start_time": start_time
                    })
            except:
                continue
        
        if not active_orders:
            print_warning("No active orders found!")
            print_info("All orders are either completed or already cancelled")
            return
        
        # Display active orders
        print(f"\n{Colors.BOLD}📋 Active Orders:{Colors.END}")
        for i, order in enumerate(active_orders, 1):
            print(f"{Colors.GREEN}  {i}.{Colors.END} {order['order_id']} (started at {order['start_time']})")
        
        print(f"{Colors.RED}  0.{Colors.END} Back to menu")
        print()
        
        # Get user choice
        choice = get_user_input(f"Select order to cancel (1-{len(active_orders)}, 0 to go back): ")
        
        if choice == "0" or not choice:
            print_info("Returning to main menu")
            return
        
        try:
            choice_idx = int(choice) - 1
            if choice_idx < 0 or choice_idx >= len(active_orders):
                print_error("Invalid selection!")
                return
        except ValueError:
            print_error("Please enter a valid number!")
            return
        
        selected_order = active_orders[choice_idx]
        order_id = selected_order["order_id"]
        
        # Double confirmation for cancellation
        print(f"\n{Colors.RED}⚠️  You are about to cancel order {order_id}{Colors.END}")
        confirm = get_user_input(f"Are you absolutely sure? This cannot be undone! (y/N): ", Colors.RED)
        if confirm.lower() != 'y':
            print_info("Cancellation aborted")
            return
        
        # Send cancellation signal
        handle = client.get_workflow_handle(selected_order["workflow_id"])
        
        print(f"\n{Colors.YELLOW}📤 Sending cancellation signal...{Colors.END}")
        await handle.signal(OrderWorkflow.cancel_order)
        
        print_success(f"Cancellation signal sent to order {order_id}")
        print_info("The workflow will handle the cancellation...")
        
    except Exception as e:
        print_error(f"Failed to cancel order: {e}")



async def main():
    """Main interactive CLI loop."""
    print_banner()
    
    # Connect to Temporal
    client = await connect_to_temporal()
    if not client:
        print_error("Cannot continue without Temporal connection. Exiting.")
        return
    
    while True:
        try:
            print_menu()
            choice = get_user_input("Choose an option (1-6, q): ", Colors.BOLD)
            
            if choice == 'q' or choice.lower() == 'quit':
                print(f"\n{Colors.CYAN}👋 Thanks for using Arjun's Temporal Demo!{Colors.END}")
                #print(f"{Colors.BLUE}May your workflows be ever resilient! ⚡{Colors.END}\n")
                break
            
            elif choice == '1':
                await start_order_interactive(client)
            
            elif choice == '2':
                await check_status_interactive(client)
            
            elif choice == '3':
                await approve_order_interactive(client)
            
            elif choice == '4':
                await update_address_interactive(client)
            
            elif choice == '5':
                await cancel_order_interactive(client)
            
            elif choice == '6':
                await view_audit_logs_interactive(client)
            
            else:
                print_error(f"Invalid choice: {choice}")
                print_info("Please choose 1-6 or 'q' to quit")
            
            # Pause before showing menu again
            input(f"\n{Colors.CYAN}Press Enter to continue...{Colors.END}")
            print("\n" + "="*60)
            
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}👋 Caught Ctrl+C. Goodbye!{Colors.END}\n")
            break
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            print_info("Continuing...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}👋 Goodbye!{Colors.END}")