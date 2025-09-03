-- Add retry tracking and enhanced observability
-- Adds columns for tracking activity attempts and retries

-- Add retry tracking to events table
ALTER TABLE events ADD COLUMN IF NOT EXISTS attempt_number INTEGER DEFAULT 1;
ALTER TABLE events ADD COLUMN IF NOT EXISTS retry_reason TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS execution_time_ms INTEGER;

-- Add retry tracking to payments table  
ALTER TABLE payments ADD COLUMN IF NOT EXISTS attempt_number INTEGER DEFAULT 1;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS last_error TEXT;

-- Create activity_attempts table for detailed retry tracking
CREATE TABLE IF NOT EXISTS activity_attempts (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(255) NOT NULL REFERENCES orders(id),
    activity_name VARCHAR(100) NOT NULL,     -- receive_order, validate_order, charge_payment, etc.
    attempt_number INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,             -- started, completed, failed, timeout
    input_data JSONB,                        -- Activity input parameters
    output_data JSONB,                       -- Activity output (if successful)
    error_message TEXT,                      -- Error details (if failed)
    execution_time_ms INTEGER,               -- How long the attempt took
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for retry tracking queries
CREATE INDEX IF NOT EXISTS idx_activity_attempts_order_id ON activity_attempts(order_id);
CREATE INDEX IF NOT EXISTS idx_activity_attempts_activity ON activity_attempts(activity_name);
CREATE INDEX IF NOT EXISTS idx_activity_attempts_status ON activity_attempts(status);
CREATE INDEX IF NOT EXISTS idx_activity_attempts_started_at ON activity_attempts(started_at);

-- Enhanced events indexes
CREATE INDEX IF NOT EXISTS idx_events_attempt_number ON events(attempt_number);
CREATE INDEX IF NOT EXISTS idx_events_execution_time ON events(execution_time_ms);

-- Enhanced payments indexes  
CREATE INDEX IF NOT EXISTS idx_payments_attempt_number ON payments(attempt_number);
CREATE INDEX IF NOT EXISTS idx_payments_retry_count ON payments(retry_count);

-- View for easy retry analysis
CREATE OR REPLACE VIEW order_retry_summary AS
SELECT 
    o.id as order_id,
    o.state as current_state,
    o.created_at,
    COUNT(aa.id) as total_activity_attempts,
    COUNT(CASE WHEN aa.status = 'failed' THEN 1 END) as failed_attempts,
    COUNT(CASE WHEN aa.status = 'completed' THEN 1 END) as successful_attempts,
    MAX(p.retry_count) as max_payment_retries,
    COUNT(DISTINCT aa.activity_name) as activities_attempted
FROM orders o
LEFT JOIN activity_attempts aa ON o.id = aa.order_id
LEFT JOIN payments p ON o.id = p.order_id
GROUP BY o.id, o.state, o.created_at
ORDER BY o.created_at DESC;

-- View for activity performance analysis
CREATE OR REPLACE VIEW activity_performance AS
SELECT 
    activity_name,
    COUNT(*) as total_attempts,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_attempts,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_attempts,
    COUNT(CASE WHEN status = 'timeout' THEN 1 END) as timeout_attempts,
    ROUND(AVG(execution_time_ms), 2) as avg_execution_time_ms,
    MAX(execution_time_ms) as max_execution_time_ms,
    MIN(execution_time_ms) as min_execution_time_ms
FROM activity_attempts
WHERE completed_at IS NOT NULL
GROUP BY activity_name
ORDER BY total_attempts DESC;