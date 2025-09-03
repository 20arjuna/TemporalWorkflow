#!/usr/bin/env python3
"""
CLI tool for managing orders via Temporal workflows.
Usage examples:
  python3 cli_or_api/order_cli.py start O-123 --address '{"line1":"123 Main St","city":"Omaha","zip":"68102"}'
  python3 cli_or_api/order_cli.py cancel O-123
  python3 cli_or_api/order_cli.py status O-123
  python3 cli_or_api/order_cli.py approve O-123
"""

import asyncio
import argparse
import json
import sys
import os
from temporalio.client import Client

# Add parent directory to Python path so we can import workflows
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workflows.order_workflow import OrderWorkflow

async def start_order(order_id: str, address: dict):
    """Start an order workflow."""
    client = await Client.connect("localhost:7233")
    try:
        handle = await client.start_workflow(
            OrderWorkflow.run,
            args=[order_id, address],
            id=f"order-{order_id}",
            task_queue="orders-tq",
        )
        print(f"✅ Started order workflow for {order_id}")
        print(f"   Workflow ID: {handle.id}")
        print(f"   Run ID: {handle.result_run_id}")
        return handle
    except Exception as e:
        print(f"❌ Failed to start workflow: {e}")
        return None

async def cancel_order(order_id: str):
    """Send cancel signal to order workflow."""
    client = await Client.connect("localhost:7233")
    try:
        handle = client.get_workflow_handle(f"order-{order_id}")
        await handle.signal(OrderWorkflow.cancel_order)
        print(f"✅ Sent cancel signal to order {order_id}")
    except Exception as e:
        print(f"❌ Failed to cancel workflow: {e}")

async def approve_order(order_id: str):
    """Send approve signal to order workflow."""
    client = await Client.connect("localhost:7233")
    try:
        handle = client.get_workflow_handle(f"order-{order_id}")
        await handle.signal(OrderWorkflow.approve)
        print(f"✅ Sent approve signal to order {order_id}")
    except Exception as e:
        print(f"❌ Failed to approve workflow: {e}")

async def get_order_status(order_id: str):
    """Get the status of an order workflow."""
    client = await Client.connect("localhost:7233")
    try:
        handle = client.get_workflow_handle(f"order-{order_id}")
        try:
            # Try to get result (non-blocking)
            result = await handle.result(timeout=0.1)
            print(f"✅ Order {order_id}: COMPLETED")
            print(f"   Result: {result}")
        except:
            # Still running
            description = await handle.describe()
            print(f"🔄 Order {order_id}: {description.status.name}")
            print(f"   Workflow ID: {handle.id}")
            print(f"   Run ID: {description.run_id}")
    except Exception as e:
        print(f"❌ Order {order_id}: NOT FOUND")
        print(f"   Error: {e}")

async def main():
    parser = argparse.ArgumentParser(description="Order Management CLI")
    parser.add_argument("command", choices=["start", "cancel", "status", "approve"], 
                       help="Command to execute")
    parser.add_argument("order_id", help="Order ID")
    parser.add_argument("--address", help="Shipping address (JSON string, required for start)")
    
    args = parser.parse_args()
    
    if args.command == "start":
        if not args.address:
            print("❌ --address is required for start command")
            print('Example: --address \'{"line1":"123 Main St","city":"Omaha","zip":"68102"}\'')
            return
        try:
            address = json.loads(args.address)
        except json.JSONDecodeError:
            print("❌ Invalid JSON in --address")
            return
        await start_order(args.order_id, address)
    
    elif args.command == "cancel":
        await cancel_order(args.order_id)
    
    elif args.command == "approve":
        await approve_order(args.order_id)
        
    elif args.command == "status":
        await get_order_status(args.order_id)

if __name__ == "__main__":
    asyncio.run(main())