"""
Database query functions for Trellis Takehome.
High-level database operations for orders, payments, and events.
"""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from .connection import fetch_one, fetch_all, fetch_value, execute_query, DatabaseManager

class OrderQueries:
    """Database queries for order management."""
    
    @staticmethod
    async def create_order(order_id: str, address: Dict[str, Any], initial_state: str = "pending") -> bool:
        """Create a new order in the database."""
        try:
            address_json = DatabaseManager.prepare_json_field(address)
            await execute_query("""
                INSERT INTO orders (id, state, address_json)
                VALUES ($1, $2, $3)
            """, order_id, initial_state, address_json)
            return True
        except Exception as e:
            print(f"❌ Failed to create order {order_id}: {e}")
            return False
    
    @staticmethod
    async def get_order(order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by ID with parsed JSON fields."""
        order = await fetch_one("SELECT * FROM orders WHERE id = $1", order_id)
        if order:
            order['address_json'] = DatabaseManager.parse_json_field(order['address_json'])
        return order
    
    @staticmethod
    async def update_order_state(order_id: str, new_state: str) -> bool:
        """Update order state."""
        try:
            result = await execute_query("""
                UPDATE orders SET state = $1 WHERE id = $2
            """, new_state, order_id)
            return "UPDATE 1" in result
        except Exception as e:
            print(f"❌ Failed to update order {order_id} state: {e}")
            return False
    
    @staticmethod
    async def update_order_address(order_id: str, new_address: Dict[str, Any]) -> bool:
        """Update order address."""
        try:
            address_json = DatabaseManager.prepare_json_field(new_address)
            result = await execute_query("""
                UPDATE orders SET address_json = $1 WHERE id = $2
            """, address_json, order_id)
            return "UPDATE 1" in result
        except Exception as e:
            print(f"❌ Failed to update order {order_id} address: {e}")
            return False
    
    @staticmethod
    async def get_recent_orders(limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent orders, most recent first."""
        orders = await fetch_all("""
            SELECT * FROM orders 
            ORDER BY created_at DESC 
            LIMIT $1
        """, limit)
        
        # Parse JSON fields
        for order in orders:
            order['address_json'] = DatabaseManager.parse_json_field(order['address_json'])
        
        return orders
    
    @staticmethod
    async def get_orders_by_state(state: str) -> List[Dict[str, Any]]:
        """Get all orders in a specific state."""
        orders = await fetch_all("""
            SELECT * FROM orders 
            WHERE state = $1 
            ORDER BY created_at DESC
        """, state)
        
        # Parse JSON fields
        for order in orders:
            order['address_json'] = DatabaseManager.parse_json_field(order['address_json'])
        
        return orders

class PaymentQueries:
    """Database queries for payment management."""
    
    @staticmethod
    async def create_payment(payment_id: str, order_id: str, amount: float, status: str = "pending") -> bool:
        """Create a payment record (idempotent)."""
        try:
            await execute_query("""
                INSERT INTO payments (payment_id, order_id, status, amount)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (payment_id) DO NOTHING
            """, payment_id, order_id, status, amount)
            return True
        except Exception as e:
            print(f"❌ Failed to create payment {payment_id}: {e}")
            return False
    
    @staticmethod
    async def update_payment_status(payment_id: str, new_status: str) -> bool:
        """Update payment status."""
        try:
            result = await execute_query("""
                UPDATE payments SET status = $1 WHERE payment_id = $2
            """, new_status, payment_id)
            return "UPDATE 1" in result
        except Exception as e:
            print(f"❌ Failed to update payment {payment_id}: {e}")
            return False
    
    @staticmethod
    async def get_payment(payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment by payment_id."""
        return await fetch_one("SELECT * FROM payments WHERE payment_id = $1", payment_id)
    
    @staticmethod
    async def get_payments_for_order(order_id: str) -> List[Dict[str, Any]]:
        """Get all payments for an order."""
        return await fetch_all("""
            SELECT * FROM payments 
            WHERE order_id = $1 
            ORDER BY created_at DESC
        """, order_id)
    
    @staticmethod
    async def is_payment_processed(payment_id: str) -> bool:
        """Check if a payment has already been processed (for idempotency)."""
        count = await fetch_value("""
            SELECT COUNT(*) FROM payments 
            WHERE payment_id = $1 AND status != 'pending'
        """, payment_id)
        return count > 0
    
    @staticmethod
    async def update_payment_retry_info(payment_id: str, attempt_number: int, retry_count: int, last_error: str = None) -> bool:
        """Update payment retry information."""
        try:
            await execute_query("""
                UPDATE payments 
                SET attempt_number = $2, retry_count = $3, last_error = $4
                WHERE payment_id = $1
            """, payment_id, attempt_number, retry_count, last_error)
            return True
        except Exception as e:
            print(f"❌ Failed to update payment retry info: {e}")
            return False

class EventQueries:
    """Database queries for event logging and audit trail."""
    
    @staticmethod
    async def log_event(order_id: str, event_type: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        """Log an event for an order."""
        try:
            payload_json = DatabaseManager.prepare_json_field(payload) if payload else None
            await execute_query("""
                INSERT INTO events (order_id, event_type, payload_json)
                VALUES ($1, $2, $3)
            """, order_id, event_type, payload_json)
            return True
        except Exception as e:
            print(f"❌ Failed to log event {event_type} for order {order_id}: {e}")
            return False
    
    @staticmethod
    async def get_order_events(order_id: str) -> List[Dict[str, Any]]:
        """Get all events for an order, chronologically."""
        events = await fetch_all("""
            SELECT * FROM events 
            WHERE order_id = $1 
            ORDER BY ts ASC
        """, order_id)
        
        # Parse JSON payloads
        for event in events:
            if event['payload_json']:
                event['payload_json'] = DatabaseManager.parse_json_field(event['payload_json'])
        
        return events
    
    @staticmethod
    async def get_recent_events(limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent events across all orders."""
        events = await fetch_all("""
            SELECT * FROM events 
            ORDER BY ts DESC 
            LIMIT $1
        """, limit)
        
        # Parse JSON payloads
        for event in events:
            if event['payload_json']:
                event['payload_json'] = DatabaseManager.parse_json_field(event['payload_json'])
        
        return events
    
    @staticmethod
    async def get_events_by_type(event_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get events of a specific type."""
        events = await fetch_all("""
            SELECT * FROM events 
            WHERE event_type = $1 
            ORDER BY ts DESC 
            LIMIT $2
        """, event_type, limit)
        
        # Parse JSON payloads
        for event in events:
            if event['payload_json']:
                event['payload_json'] = DatabaseManager.parse_json_field(event['payload_json'])
        
        return events

class DatabaseStats:
    """Database statistics and monitoring queries."""
    
    @staticmethod
    async def get_order_stats() -> Dict[str, Any]:
        """Get order statistics by state."""
        stats = await fetch_all("""
            SELECT state, COUNT(*) as count
            FROM orders 
            GROUP BY state
            ORDER BY count DESC
        """)
        
        total = await fetch_value("SELECT COUNT(*) FROM orders")
        
        return {
            "total_orders": total,
            "by_state": {stat['state']: stat['count'] for stat in stats}
        }
    
    @staticmethod
    async def get_payment_stats() -> Dict[str, Any]:
        """Get payment statistics."""
        stats = await fetch_all("""
            SELECT status, COUNT(*) as count, SUM(amount) as total_amount
            FROM payments 
            GROUP BY status
            ORDER BY count DESC
        """)
        
        total_payments = await fetch_value("SELECT COUNT(*) FROM payments")
        total_amount = await fetch_value("SELECT SUM(amount) FROM payments WHERE status = 'charged'")
        
        return {
            "total_payments": total_payments,
            "total_charged_amount": float(total_amount) if total_amount else 0.0,
            "by_status": {
                stat['status']: {
                    "count": stat['count'], 
                    "total_amount": float(stat['total_amount']) if stat['total_amount'] else 0.0
                } 
                for stat in stats
            }
        }
    
    @staticmethod
    async def get_recent_activity(hours: int = 24) -> Dict[str, Any]:
        """Get recent activity in the last N hours."""
        recent_orders = await fetch_value(f"""
            SELECT COUNT(*) FROM orders 
            WHERE created_at > NOW() - INTERVAL '{hours} hours'
        """)
        
        recent_events = await fetch_value(f"""
            SELECT COUNT(*) FROM events 
            WHERE ts > NOW() - INTERVAL '{hours} hours'
        """)
        
        recent_payments = await fetch_value(f"""
            SELECT COUNT(*) FROM payments 
            WHERE created_at > NOW() - INTERVAL '{hours} hours'
        """)
        
        return {
            "timeframe_hours": hours,
            "new_orders": recent_orders,
            "total_events": recent_events,
            "new_payments": recent_payments
        }

# Utility functions for common patterns
async def with_transaction(operation):
    """Execute an operation within a database transaction."""
    async with get_db_connection() as conn:
        async with conn.transaction():
            return await operation(conn)

async def ensure_order_exists(order_id: str, address: Dict[str, Any]) -> bool:
    """Ensure an order exists, create if it doesn't (idempotent)."""
    existing = await OrderQueries.get_order(order_id)
    if existing:
        return True
    
    return await OrderQueries.create_order(order_id, address)

class RetryQueries:
    """Database queries for retry tracking and observability."""
    
    @staticmethod
    async def log_activity_attempt(
        order_id: str, 
        activity_name: str, 
        attempt_number: int,
        status: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None
    ) -> bool:
        """Log an activity attempt for retry tracking."""
        try:
            input_json = DatabaseManager.prepare_json_field(input_data) if input_data else None
            output_json = DatabaseManager.prepare_json_field(output_data) if output_data else None
            
            await execute_query("""
                INSERT INTO activity_attempts 
                (order_id, activity_name, attempt_number, status, input_data, output_data, 
                 error_message, execution_time_ms, completed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, order_id, activity_name, attempt_number, status, input_json, output_json,
                error_message, execution_time_ms, 
                datetime.utcnow() if status in ['completed', 'failed', 'timeout'] else None)
            return True
        except Exception as e:
            print(f"❌ Failed to log activity attempt: {e}")
            return False
    
    @staticmethod
    async def get_order_attempts(order_id: str) -> List[Dict[str, Any]]:
        """Get all activity attempts for an order."""
        attempts = await fetch_all("""
            SELECT * FROM activity_attempts 
            WHERE order_id = $1 
            ORDER BY started_at ASC
        """, order_id)
        
        # Parse JSON fields
        for attempt in attempts:
            if attempt['input_data']:
                attempt['input_data'] = DatabaseManager.parse_json_field(attempt['input_data'])
            if attempt['output_data']:
                attempt['output_data'] = DatabaseManager.parse_json_field(attempt['output_data'])
        
        return attempts
    
    @staticmethod
    async def get_activity_performance() -> List[Dict[str, Any]]:
        """Get activity performance statistics."""
        return await fetch_all("SELECT * FROM activity_performance ORDER BY total_attempts DESC")
    
    @staticmethod
    async def get_order_retry_summary(order_id: str) -> Optional[Dict[str, Any]]:
        """Get retry summary for a specific order."""
        return await fetch_one("SELECT * FROM order_retry_summary WHERE order_id = $1", order_id)
    
    @staticmethod
    async def get_all_retry_summaries(limit: int = 10) -> List[Dict[str, Any]]:
        """Get retry summaries for recent orders."""
        return await fetch_all("SELECT * FROM order_retry_summary LIMIT $1", limit)
    
    @staticmethod
    async def get_failed_activities(hours: int = 24) -> List[Dict[str, Any]]:
        """Get failed activities in the last N hours."""
        attempts = await fetch_all(f"""
            SELECT * FROM activity_attempts 
            WHERE status = 'failed' 
            AND started_at > NOW() - INTERVAL '{hours} hours'
            ORDER BY started_at DESC
        """)
        
        # Parse JSON fields
        for attempt in attempts:
            if attempt['input_data']:
                attempt['input_data'] = DatabaseManager.parse_json_field(attempt['input_data'])
            if attempt['output_data']:
                attempt['output_data'] = DatabaseManager.parse_json_field(attempt['output_data'])
        
        return attempts

class ObservabilityQueries:
    """Advanced observability and monitoring queries."""
    
    @staticmethod
    async def get_order_health_report(order_id: str) -> Dict[str, Any]:
        """Get comprehensive health report for an order."""
        # Get basic order info
        order = await OrderQueries.get_order(order_id)
        if not order:
            return {"error": "Order not found"}
        
        # Get retry summary
        retry_summary = await RetryQueries.get_order_retry_summary(order_id)
        
        # Get all attempts
        attempts = await RetryQueries.get_order_attempts(order_id)
        
        # Get payments
        payments = await PaymentQueries.get_payments_for_order(order_id)
        
        # Get events
        events = await EventQueries.get_order_events(order_id)
        
        # Calculate health metrics
        total_attempts = len(attempts)
        failed_attempts = len([a for a in attempts if a['status'] == 'failed'])
        success_rate = (total_attempts - failed_attempts) / total_attempts if total_attempts > 0 else 1.0
        
        # Calculate average execution time
        completed_attempts = [a for a in attempts if a['execution_time_ms'] is not None]
        avg_execution_time = sum(a['execution_time_ms'] for a in completed_attempts) / len(completed_attempts) if completed_attempts else 0
        
        return {
            "order": order,
            "retry_summary": retry_summary,
            "health_metrics": {
                "success_rate": round(success_rate * 100, 1),
                "total_attempts": total_attempts,
                "failed_attempts": failed_attempts,
                "avg_execution_time_ms": round(avg_execution_time, 1),
                "payment_retries": max((p.get('retry_count', 0) for p in payments), default=0)
            },
            "timeline": {
                "events": events,
                "attempts": attempts,
                "payments": payments
            }
        }
    
    @staticmethod
    async def get_system_health_dashboard() -> Dict[str, Any]:
        """Get system-wide health and performance dashboard."""
        # Get activity performance
        activity_perf = await RetryQueries.get_activity_performance()
        
        # Get recent failures
        recent_failures = await RetryQueries.get_failed_activities(24)
        
        # Get order stats
        order_stats = await DatabaseStats.get_order_stats()
        payment_stats = await DatabaseStats.get_payment_stats()
        recent_activity = await DatabaseStats.get_recent_activity(24)
        
        # Get retry summaries
        retry_summaries = await RetryQueries.get_all_retry_summaries(10)
        
        # Calculate system health score
        total_orders = order_stats.get('total_orders', 0)
        failed_orders = order_stats.get('by_state', {}).get('validation_failed', 0) + order_stats.get('by_state', {}).get('payment_failed', 0)
        system_success_rate = (total_orders - failed_orders) / total_orders if total_orders > 0 else 1.0
        
        return {
            "system_health": {
                "success_rate": round(system_success_rate * 100, 1),
                "total_orders": total_orders,
                "failed_orders": failed_orders,
                "recent_failures_24h": len(recent_failures)
            },
            "activity_performance": activity_perf,
            "recent_failures": recent_failures[:5],  # Top 5 recent failures
            "order_stats": order_stats,
            "payment_stats": payment_stats,
            "recent_activity": recent_activity,
            "retry_summaries": retry_summaries
        }