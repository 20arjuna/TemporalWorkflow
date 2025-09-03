-- Initial database schema for Trellis Takehome
-- Creates tables for orders, payments, and events

-- Orders table - main order state and metadata
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(255) PRIMARY KEY,           -- Order ID (O-123, O-456, etc.)
    state VARCHAR(50) NOT NULL,            -- pending, approved, shipped, cancelled, failed
    address_json JSONB NOT NULL,           -- Shipping address as JSON
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Payments table - payment transactions with idempotency
CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(255) PRIMARY KEY,   -- Idempotent key (order_id + attempt)
    order_id VARCHAR(255) NOT NULL REFERENCES orders(id),
    status VARCHAR(50) NOT NULL,           -- pending, charged, failed
    amount DECIMAL(10,2),                  -- Payment amount
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Events table - audit trail for debugging and monitoring
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(255) NOT NULL REFERENCES orders(id),
    event_type VARCHAR(100) NOT NULL,      -- order_created, payment_charged, package_prepared, etc.
    payload_json JSONB,                    -- Event details and metadata
    ts TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_orders_state ON orders(state);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_events_order_id ON events(order_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at on orders table
CREATE TRIGGER update_orders_updated_at 
    BEFORE UPDATE ON orders 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Insert some sample data for testing (optional)
-- INSERT INTO orders (id, state, address_json) VALUES 
-- ('O-SAMPLE', 'pending', '{"line1": "123 Test St", "city": "Test City", "zip": "12345"}')
-- ON CONFLICT (id) DO NOTHING;