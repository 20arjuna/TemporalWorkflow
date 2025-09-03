"""
Unit tests for database setup and migration functionality.
Tests database connection, table creation, and basic CRUD operations.
"""

import pytest
import asyncio
import asyncpg
import sys
import os
from datetime import datetime

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database connection settings (same as migration script)
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "user": "trellis", 
    "password": "trellis",
    "database": "trellis"
}

class TestDatabaseSetup:
    """Test database setup and migration functionality."""

    @pytest.mark.asyncio
    async def test_database_connection(self):
        """Test that we can connect to the PostgreSQL database."""
        try:
            conn = await asyncpg.connect(**DB_CONFIG)
            
            # Test basic query
            result = await conn.fetchval("SELECT 1")
            assert result == 1
            
            await conn.close()
        except Exception as e:
            pytest.fail(f"Database connection failed: {e}")

    @pytest.mark.asyncio
    async def test_required_tables_exist(self):
        """Test that all required tables were created by migrations."""
        conn = await asyncpg.connect(**DB_CONFIG)
        
        try:
            # Check that all required tables exist
            tables = await conn.fetch("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            
            table_names = {table['tablename'] for table in tables}
            
            # Verify all required tables exist
            required_tables = {'orders', 'payments', 'events', 'schema_migrations'}
            assert required_tables.issubset(table_names), f"Missing tables: {required_tables - table_names}"
            
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_orders_table_structure(self):
        """Test orders table has correct columns and types."""
        conn = await asyncpg.connect(**DB_CONFIG)
        
        try:
            # Get table structure
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'orders'
                ORDER BY column_name
            """)
            
            column_info = {col['column_name']: col for col in columns}
            
            # Check required columns exist
            assert 'id' in column_info
            assert 'state' in column_info
            assert 'address_json' in column_info
            assert 'created_at' in column_info
            assert 'updated_at' in column_info
            
            # Check data types
            assert 'character varying' in column_info['id']['data_type']
            assert 'jsonb' in column_info['address_json']['data_type']
            
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_payments_table_structure(self):
        """Test payments table has correct columns and constraints."""
        conn = await asyncpg.connect(**DB_CONFIG)
        
        try:
            # Get table structure
            columns = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'payments'
                ORDER BY column_name
            """)
            
            column_info = {col['column_name']: col for col in columns}
            
            # Check required columns exist
            assert 'payment_id' in column_info
            assert 'order_id' in column_info
            assert 'status' in column_info
            assert 'amount' in column_info
            assert 'created_at' in column_info
            
            # Check numeric type for amount
            assert 'numeric' in column_info['amount']['data_type']
            
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_events_table_structure(self):
        """Test events table has correct columns."""
        conn = await asyncpg.connect(**DB_CONFIG)
        
        try:
            columns = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'events'
                ORDER BY column_name
            """)
            
            column_info = {col['column_name']: col for col in columns}
            
            # Check required columns exist
            assert 'id' in column_info
            assert 'order_id' in column_info
            assert 'event_type' in column_info
            assert 'payload_json' in column_info
            assert 'ts' in column_info
            
            # Check JSONB type for payload
            assert 'jsonb' in column_info['payload_json']['data_type']
            
        finally:
            await conn.close()

class TestDatabaseOperations:
    """Test basic database operations."""

    @pytest.mark.asyncio
    async def test_insert_order(self):
        """Test inserting a new order."""
        conn = await asyncpg.connect(**DB_CONFIG)
        
        # Clean up any existing test data
        await conn.execute("DELETE FROM orders WHERE id = 'TEST-ORDER'")
        
        # Insert test order
        import json
        address_json = json.dumps({"line1": "123 Test St", "city": "Test City", "zip": "12345"})
        await conn.execute("""
            INSERT INTO orders (id, state, address_json)
            VALUES ($1, $2, $3)
        """, 'TEST-ORDER', 'pending', address_json)
        
        # Verify order was inserted
        order = await conn.fetchrow("SELECT * FROM orders WHERE id = 'TEST-ORDER'")
        assert order is not None
        assert order['id'] == 'TEST-ORDER'
        assert order['state'] == 'pending'
        # Parse JSON for comparison
        address_data = json.loads(order['address_json']) if isinstance(order['address_json'], str) else order['address_json']
        assert address_data['city'] == 'Test City'
        
        # Clean up
        await conn.execute("DELETE FROM orders WHERE id = 'TEST-ORDER'")
        await conn.close()

    @pytest.mark.asyncio
    async def test_payment_idempotency(self):
        """Test payment idempotency with ON CONFLICT."""
        conn = await asyncpg.connect(**DB_CONFIG)
        
        # Clean up any existing test data
        await conn.execute("DELETE FROM payments WHERE payment_id = 'TEST-PAYMENT-1'")
        await conn.execute("DELETE FROM orders WHERE id = 'TEST-ORDER-PAY'")
        
        # Insert test order first
        await conn.execute("""
            INSERT INTO orders (id, state, address_json)
            VALUES ($1, $2, $3)
        """, 'TEST-ORDER-PAY', 'pending', '{"line1": "123 Test St"}')
        
        # Insert payment (first time)
        result1 = await conn.execute("""
            INSERT INTO payments (payment_id, order_id, status, amount)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (payment_id) DO NOTHING
        """, 'TEST-PAYMENT-1', 'TEST-ORDER-PAY', 'charged', 99.99)
        
        # Insert same payment (should be idempotent)
        result2 = await conn.execute("""
            INSERT INTO payments (payment_id, order_id, status, amount)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (payment_id) DO NOTHING
        """, 'TEST-PAYMENT-1', 'TEST-ORDER-PAY', 'charged', 99.99)
        
        # Verify only one payment exists
        count = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE payment_id = 'TEST-PAYMENT-1'")
        assert count == 1
        
        # Clean up
        await conn.execute("DELETE FROM payments WHERE payment_id = 'TEST-PAYMENT-1'")
        await conn.execute("DELETE FROM orders WHERE id = 'TEST-ORDER-PAY'")
        await conn.close()

    @pytest.mark.asyncio
    async def test_events_logging(self):
        """Test event logging functionality."""
        conn = await asyncpg.connect(**DB_CONFIG)
        
        # Clean up any existing test data
        await conn.execute("DELETE FROM events WHERE order_id = 'TEST-ORDER-EVENTS'")
        await conn.execute("DELETE FROM orders WHERE id = 'TEST-ORDER-EVENTS'")
        
        # Insert test order
        await conn.execute("""
            INSERT INTO orders (id, state, address_json)
            VALUES ($1, $2, $3)
        """, 'TEST-ORDER-EVENTS', 'pending', '{"line1": "123 Test St"}')
        
        # Insert test events
        import json
        event1_payload = json.dumps({"source": "test", "timestamp": "2024-01-01T12:00:00Z"})
        event2_payload = json.dumps({"amount": 99.99, "payment_id": "test-payment"})
        
        await conn.execute("""
            INSERT INTO events (order_id, event_type, payload_json)
            VALUES ($1, $2, $3)
        """, 'TEST-ORDER-EVENTS', 'order_created', event1_payload)
        
        await conn.execute("""
            INSERT INTO events (order_id, event_type, payload_json)
            VALUES ($1, $2, $3)
        """, 'TEST-ORDER-EVENTS', 'payment_charged', event2_payload)
        
        # Verify events were inserted
        events = await conn.fetch("SELECT * FROM events WHERE order_id = 'TEST-ORDER-EVENTS' ORDER BY ts")
        assert len(events) == 2
        assert events[0]['event_type'] == 'order_created'
        assert events[1]['event_type'] == 'payment_charged'
        # Parse JSON for comparison
        payload_data = json.loads(events[1]['payload_json']) if isinstance(events[1]['payload_json'], str) else events[1]['payload_json']
        assert payload_data['amount'] == 99.99
        
        # Clean up
        await conn.execute("DELETE FROM events WHERE order_id = 'TEST-ORDER-EVENTS'")
        await conn.execute("DELETE FROM orders WHERE id = 'TEST-ORDER-EVENTS'")
        await conn.close()

    @pytest.mark.asyncio
    async def test_updated_at_trigger(self):
        """Test that updated_at timestamp is automatically updated."""
        conn = await asyncpg.connect(**DB_CONFIG)
        
        # Clean up any existing test data
        await conn.execute("DELETE FROM orders WHERE id = 'TEST-UPDATE'")
        
        # Insert test order
        await conn.execute("""
            INSERT INTO orders (id, state, address_json)
            VALUES ($1, $2, $3)
        """, 'TEST-UPDATE', 'pending', '{"line1": "123 Test St"}')
        
        # Get initial timestamps
        initial = await conn.fetchrow("SELECT created_at, updated_at FROM orders WHERE id = 'TEST-UPDATE'")
        
        # Wait a moment then update
        await asyncio.sleep(0.1)
        await conn.execute("UPDATE orders SET state = 'approved' WHERE id = 'TEST-UPDATE'")
        
        # Get updated timestamps
        updated = await conn.fetchrow("SELECT created_at, updated_at FROM orders WHERE id = 'TEST-UPDATE'")
        
        # Verify updated_at changed but created_at didn't
        assert updated['created_at'] == initial['created_at']
        assert updated['updated_at'] > initial['updated_at']
        
        # Clean up
        await conn.execute("DELETE FROM orders WHERE id = 'TEST-UPDATE'")
        await conn.close()

class TestDatabaseIntegration:
    """Test database integration scenarios."""

    @pytest.mark.asyncio
    async def test_order_lifecycle_in_db(self):
        """Test complete order lifecycle database operations."""
        conn = await asyncpg.connect(**DB_CONFIG)
        order_id = 'TEST-LIFECYCLE'
        
        # Clean up any existing test data
        await conn.execute("DELETE FROM events WHERE order_id = $1", order_id)
        await conn.execute("DELETE FROM payments WHERE order_id = $1", order_id)
        await conn.execute("DELETE FROM orders WHERE id = $1", order_id)
        
        try:
            # 1. Create order
            import json
            await conn.execute("""
                INSERT INTO orders (id, state, address_json)
                VALUES ($1, $2, $3)
            """, order_id, 'pending', json.dumps({"line1": "123 Lifecycle St", "city": "Test City", "zip": "12345"}))
            
            # 2. Log order creation event
            await conn.execute("""
                INSERT INTO events (order_id, event_type, payload_json)
                VALUES ($1, $2, $3)
            """, order_id, 'order_created', json.dumps({"source": "test"}))
            
            # 3. Approve order
            await conn.execute("UPDATE orders SET state = 'approved' WHERE id = $1", order_id)
            
            # 4. Process payment (idempotent)
            payment_id = f"{order_id}-attempt-1"
            await conn.execute("""
                INSERT INTO payments (payment_id, order_id, status, amount)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (payment_id) DO NOTHING
            """, payment_id, order_id, 'charged', 99.99)
            
            # 5. Log payment event
            await conn.execute("""
                INSERT INTO events (order_id, event_type, payload_json)
                VALUES ($1, $2, $3)
            """, order_id, 'payment_charged', json.dumps({"payment_id": payment_id, "amount": 99.99}))
            
            # 6. Ship order
            await conn.execute("UPDATE orders SET state = 'shipped' WHERE id = $1", order_id)
            
            # Verify final state
            order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
            assert order['state'] == 'shipped'
            
            payment = await conn.fetchrow("SELECT * FROM payments WHERE order_id = $1", order_id)
            assert payment['status'] == 'charged'
            assert float(payment['amount']) == 99.99
            
            events = await conn.fetch("SELECT * FROM events WHERE order_id = $1 ORDER BY ts", order_id)
            assert len(events) == 2
            assert events[0]['event_type'] == 'order_created'
            assert events[1]['event_type'] == 'payment_charged'
            
        finally:
            # Clean up
            await conn.execute("DELETE FROM events WHERE order_id = $1", order_id)
            await conn.execute("DELETE FROM payments WHERE order_id = $1", order_id)
            await conn.execute("DELETE FROM orders WHERE id = $1", order_id)
            await conn.close()

    @pytest.mark.asyncio
    async def test_payment_idempotency_stress(self):
        """Test payment idempotency under multiple attempts."""
        conn = await asyncpg.connect(**DB_CONFIG)
        order_id = 'TEST-IDEMPOTENT'
        payment_id = f"{order_id}-attempt-1"
        
        # Clean up
        await conn.execute("DELETE FROM payments WHERE payment_id = $1", payment_id)
        await conn.execute("DELETE FROM orders WHERE id = $1", order_id)
        
        try:
            # Create test order
            await conn.execute("""
                INSERT INTO orders (id, state, address_json)
                VALUES ($1, $2, $3)
            """, order_id, 'pending', '{"line1": "123 Test St"}')
            
            # Simulate multiple payment attempts (like retries)
            for i in range(5):
                await conn.execute("""
                    INSERT INTO payments (payment_id, order_id, status, amount)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (payment_id) DO NOTHING
                """, payment_id, order_id, 'charged', 99.99)
            
            # Should only have one payment record
            count = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE payment_id = $1", payment_id)
            assert count == 1
            
            payment = await conn.fetchrow("SELECT * FROM payments WHERE payment_id = $1", payment_id)
            assert payment['status'] == 'charged'
            assert float(payment['amount']) == 99.99
            
        finally:
            # Clean up
            await conn.execute("DELETE FROM payments WHERE payment_id = $1", payment_id)
            await conn.execute("DELETE FROM orders WHERE id = $1", order_id)
            await conn.close()

    @pytest.mark.asyncio
    async def test_json_operations(self):
        """Test JSONB operations for address and event payload."""
        conn = await asyncpg.connect(**DB_CONFIG)
        order_id = 'TEST-JSON'
        
        # Clean up
        await conn.execute("DELETE FROM orders WHERE id = $1", order_id)
        
        try:
            # Insert order with complex address JSON
            import json
            address = {
                "line1": "123 JSON Test Ave",
                "line2": "Apt 4B", 
                "city": "JSON City",
                "state": "JS",
                "zip": "12345",
                "country": "USA"
            }
            
            await conn.execute("""
                INSERT INTO orders (id, state, address_json)
                VALUES ($1, $2, $3)
            """, order_id, 'pending', json.dumps(address))
            
            # Query with JSON operations
            city = await conn.fetchval("""
                SELECT address_json->>'city' FROM orders WHERE id = $1
            """, order_id)
            assert city == "JSON City"
            
            # Update JSON field
            await conn.execute("""
                UPDATE orders 
                SET address_json = jsonb_set(address_json, '{line2}', '"Suite 5C"')
                WHERE id = $1
            """, order_id)
            
            # Verify JSON update
            updated_address_raw = await conn.fetchval("SELECT address_json FROM orders WHERE id = $1", order_id)
            updated_address = json.loads(updated_address_raw) if isinstance(updated_address_raw, str) else updated_address_raw
            assert updated_address['line2'] == "Suite 5C"
            assert updated_address['city'] == "JSON City"  # Other fields unchanged
            
        finally:
            # Clean up
            await conn.execute("DELETE FROM orders WHERE id = $1", order_id)
            await conn.close()

class TestMigrationRunner:
    """Test the migration runner functionality."""

    @pytest.mark.asyncio
    async def test_migration_tracking(self):
        """Test that migrations are properly tracked."""
        conn = await asyncpg.connect(**DB_CONFIG)
        
        try:
            # Check that migration tracking table exists
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'schema_migrations'
                )
            """)
            assert exists
            
            # Check that our migration was recorded
            migration = await conn.fetchrow("""
                SELECT * FROM schema_migrations WHERE version = '001_init'
            """)
            assert migration is not None
            assert migration['version'] == '001_init'
            
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_indexes_exist(self):
        """Test that performance indexes were created."""
        conn = await asyncpg.connect(**DB_CONFIG)
        
        try:
            # Check that indexes exist
            indexes = await conn.fetch("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename IN ('orders', 'payments', 'events')
                AND indexname LIKE 'idx_%'
            """)
            
            index_names = {idx['indexname'] for idx in indexes}
            
            # Verify key indexes exist
            expected_indexes = {
                'idx_orders_state',
                'idx_orders_created_at', 
                'idx_payments_order_id',
                'idx_events_order_id'
            }
            
            assert expected_indexes.issubset(index_names), f"Missing indexes: {expected_indexes - index_names}"
            
        finally:
            await conn.close()

# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])