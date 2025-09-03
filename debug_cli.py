#!/usr/bin/env python3
"""
Debug CLI that works without Temporal to check database state.
"""

import asyncio
import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.connection import startup_db, shutdown_db
from db.queries import OrderQueries, PaymentQueries, EventQueries

# Color codes
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

async def debug_orders():
    """Debug what's in the database."""
    print(f"{Colors.BOLD}🔍 DEBUG: What's in the database?{Colors.END}")
    print("=" * 50)
    
    try:
        await startup_db()
        
        # Check orders
        print(f"\n{Colors.CYAN}📦 ORDERS:{Colors.END}")
        orders = await OrderQueries.get_recent_orders(10)
        if orders:
            for order in orders:
                color = Colors.GREEN if order['state'] == 'shipped' else Colors.YELLOW if 'failed' not in order['state'] else Colors.RED
                print(f"   {color}{order['id']}: {order['state']} (created: {order['created_at'].strftime('%H:%M:%S')}){Colors.END}")
        else:
            print(f"   {Colors.RED}No orders found!{Colors.END}")
        
        # Check payments
        print(f"\n{Colors.CYAN}💳 PAYMENTS:{Colors.END}")
        from db.connection import fetch_all
        payments = await fetch_all("SELECT * FROM payments ORDER BY created_at DESC LIMIT 10")
        if payments:
            for payment in payments:
                color = Colors.GREEN if payment['status'] == 'charged' else Colors.RED
                print(f"   {color}{payment['payment_id']}: {payment['status']} - ${payment['amount']} (order: {payment['order_id']}){Colors.END}")
        else:
            print(f"   {Colors.RED}No payments found!{Colors.END}")
        
        # Check events
        print(f"\n{Colors.CYAN}📝 RECENT EVENTS:{Colors.END}")
        events = await EventQueries.get_recent_events(20)
        if events:
            for event in events:
                color = Colors.RED if 'failed' in event['event_type'] else Colors.GREEN if 'completed' in event['event_type'] or 'charged' in event['event_type'] else Colors.CYAN
                print(f"   {color}{event['ts'].strftime('%H:%M:%S')} - {event['order_id']} - {event['event_type']}{Colors.END}")
        else:
            print(f"   {Colors.RED}No events found!{Colors.END}")
        
        # Check activity attempts
        print(f"\n{Colors.CYAN}🔄 ACTIVITY ATTEMPTS:{Colors.END}")
        from db.connection import fetch_all
        attempts = await fetch_all("SELECT * FROM activity_attempts ORDER BY started_at DESC LIMIT 10")
        if attempts:
            for attempt in attempts:
                color = Colors.GREEN if attempt['status'] == 'completed' else Colors.RED
                print(f"   {color}{attempt['order_id']} - {attempt['activity_name']} (attempt {attempt['attempt_number']}): {attempt['status']}{Colors.END}")
                if attempt['error_message']:
                    print(f"      Error: {attempt['error_message'][:60]}...")
        else:
            print(f"   {Colors.RED}No activity attempts found!{Colors.END}")
        
        print(f"\n{Colors.BOLD}🎯 SUMMARY:{Colors.END}")
        print(f"   Orders: {len(orders)}")
        print(f"   Payments: {len(payments)}")
        print(f"   Events: {len(events)}")
        print(f"   Activity Attempts: {len(attempts)}")
        
    except Exception as e:
        print(f"{Colors.RED}❌ Database error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
    
    finally:
        await shutdown_db()

async def create_test_order():
    """Create a test order directly in the database."""
    print(f"{Colors.BOLD}🧪 Creating test order directly in database...{Colors.END}")
    
    try:
        await startup_db()
        
        order_id = "DEBUG-TEST-001"
        address = {"line1": "123 Debug St", "city": "Test City", "zip": "12345"}
        
        # Clean up existing
        from db.connection import execute_query
        await execute_query("DELETE FROM events WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM payments WHERE order_id = $1", order_id)
        await execute_query("DELETE FROM orders WHERE id = $1", order_id)
        
        # Create order
        success = await OrderQueries.create_order(order_id, address, "received")
        if success:
            print(f"   {Colors.GREEN}✅ Created order: {order_id}{Colors.END}")
            
            # Add some events
            await EventQueries.log_event(order_id, "order_received", {"source": "debug_cli"})
            await EventQueries.log_event(order_id, "validation_started", {"source": "debug_cli"})
            
            # Create payment
            await PaymentQueries.create_payment(f"{order_id}-payment-1", order_id, 99.99, "pending")
            print(f"   {Colors.GREEN}✅ Created payment and events{Colors.END}")
        else:
            print(f"   {Colors.RED}❌ Failed to create order{Colors.END}")
            
    except Exception as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
    
    finally:
        await shutdown_db()

async def main():
    """Main debug menu."""
    while True:
        print(f"\n{Colors.BOLD}🔧 DEBUG MENU:{Colors.END}")
        print(f"{Colors.GREEN}  1.{Colors.END} 🔍 Check database state")
        print(f"{Colors.GREEN}  2.{Colors.END} 🧪 Create test order")
        print(f"{Colors.RED}  q.{Colors.END} 👋 Quit")
        
        choice = input(f"\n{Colors.CYAN}Choose option: {Colors.END}").strip()
        
        if choice == 'q':
            break
        elif choice == '1':
            await debug_orders()
        elif choice == '2':
            await create_test_order()
        else:
            print(f"{Colors.RED}Invalid choice!{Colors.END}")

if __name__ == "__main__":
    asyncio.run(main())