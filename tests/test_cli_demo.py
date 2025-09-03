#!/usr/bin/env python3
"""
Demo script to show enhanced CLI functionality.
Demonstrates database-backed features.
"""

import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import CLI functions directly (avoiding Temporal imports)
from db.connection import startup_db, shutdown_db
from db.queries import OrderQueries, EventQueries, ObservabilityQueries

async def demo_enhanced_cli():
    """Demo the enhanced CLI functionality."""
    print("🎬 Enhanced CLI Demo")
    print("=" * 50)
    
    try:
        await startup_db()
        
        # Demo 1: Show order health report
        print(f"\n📊 DEMO: Order Health Report")
        print("-" * 30)
        
        orders = await OrderQueries.get_recent_orders(3)
        for order in orders:
            health_report = await ObservabilityQueries.get_order_health_report(order["id"])
            
            print(f"Order: {order['id']}")
            print(f"  State: {order['state']}")
            print(f"  Success Rate: {health_report['health_metrics']['success_rate']}%")
            print(f"  Events: {len(health_report['timeline']['events'])}")
            print(f"  Payments: {len(health_report['timeline']['payments'])}")
            print()
        
        # Demo 2: Show system dashboard
        print(f"\n📈 DEMO: System Dashboard")
        print("-" * 30)
        
        dashboard = await ObservabilityQueries.get_system_health_dashboard()
        health = dashboard["system_health"]
        
        print(f"System Health: {health['success_rate']}%")
        print(f"Total Orders: {health['total_orders']}")
        print(f"Failed Orders: {health['failed_orders']}")
        print(f"Recent Failures (24h): {health['recent_failures_24h']}")
        
        # Demo 3: Show recent events
        print(f"\n📝 DEMO: Recent Events")
        print("-" * 30)
        
        events = await EventQueries.get_recent_events(10)
        for event in events:
            print(f"{event['ts'].strftime('%H:%M:%S')} - {event['order_id']} - {event['event_type']}")
        
        print(f"\n🎉 Enhanced CLI features are working perfectly!")
        print(f"\n💡 To test interactively:")
        print(f"   python3 cli.py")
        print(f"   Try these new options:")
        print(f"   📊 Option 2: Enhanced order status with DB info")
        print(f"   🔍 Option 7: Audit logs viewer")
        print(f"   📈 Option 8: System health dashboard")
        
        return True
        
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await shutdown_db()

if __name__ == "__main__":
    asyncio.run(demo_enhanced_cli())