#!/usr/bin/env python3
"""
Test script for enhanced CLI functionality.
Tests database-backed features without user interaction.
"""

import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import startup_db, shutdown_db
from db.queries import OrderQueries, PaymentQueries, EventQueries, RetryQueries, ObservabilityQueries

async def test_enhanced_cli_functions():
    """Test the enhanced CLI functions with database integration."""
    print("🧪 Testing Enhanced CLI Functions")
    print("=" * 50)
    
    try:
        await startup_db()
        
        # Test order health report
        await test_order_health_report()
        
        # System dashboard removed - skip
        
        # Test audit queries
        await test_audit_queries()
        
        print("\n🎉 ALL CLI FUNCTIONS WORKING! Enhanced CLI is ready! 🚀")
        return True
        
    except Exception as e:
        print(f"\n💥 Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await shutdown_db()

async def test_order_health_report():
    """Test order health report functionality."""
    print(f"\n📊 Testing Order Health Report...")
    
    # Test with existing order
    orders = await OrderQueries.get_recent_orders(1)
    if not orders:
        print("   ⚠️  No orders found for testing")
        return
    
    order_id = orders[0]["id"]
    health_report = await ObservabilityQueries.get_order_health_report(order_id)
    
    assert "order" in health_report, "Health report missing order info"
    assert "health_metrics" in health_report, "Health report missing metrics"
    assert "timeline" in health_report, "Health report missing timeline"
    
    print(f"   ✅ Health report for {order_id}:")
    print(f"      State: {health_report['order']['state']}")
    print(f"      Success Rate: {health_report['health_metrics']['success_rate']}%")
    print(f"      Events: {len(health_report['timeline']['events'])}")
    print(f"      Payments: {len(health_report['timeline']['payments'])}")

async def test_system_dashboard():
    """Test system dashboard functionality."""
    print(f"\n📈 Testing System Dashboard...")
    
    dashboard = await ObservabilityQueries.get_system_health_dashboard()
    
    assert "system_health" in dashboard, "Dashboard missing system health"
    assert "activity_performance" in dashboard, "Dashboard missing activity performance"
    assert "order_stats" in dashboard, "Dashboard missing order stats"
    
    health = dashboard["system_health"]
    print(f"   ✅ System Health:")
    print(f"      Success Rate: {health['success_rate']}%")
    print(f"      Total Orders: {health['total_orders']}")
    print(f"      Failed Orders: {health['failed_orders']}")
    
    order_stats = dashboard["order_stats"]
    print(f"   ✅ Order Stats:")
    print(f"      Total: {order_stats['total_orders']}")
    print(f"      By State: {order_stats['by_state']}")

async def test_audit_queries():
    """Test audit and retry tracking queries."""
    print(f"\n🔍 Testing Audit Queries...")
    
    # Test recent events
    events = await EventQueries.get_recent_events(5)
    print(f"   ✅ Recent Events: {len(events)} found")
    
    # Test retry summaries
    summaries = await RetryQueries.get_all_retry_summaries(5)
    print(f"   ✅ Retry Summaries: {len(summaries)} found")
    
    # Test failed activities
    failures = await RetryQueries.get_failed_activities(24)
    print(f"   ✅ Recent Failures: {len(failures)} found")
    
    # Test activity performance
    performance = await RetryQueries.get_activity_performance()
    print(f"   ✅ Activity Performance: {len(performance)} activities tracked")

async def main():
    """Run enhanced CLI tests."""
    success = await test_enhanced_cli_functions()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)