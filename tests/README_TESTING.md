# Comprehensive Test Suite

This directory contains a complete test suite for the Temporal Workflow System, designed to rigorously validate all components and their interactions.

## Test Structure

### Core Test Files

1. **`test_e2e_workflow_integration.py`** - End-to-end workflow testing
   - Complete order flow simulation through database
   - Order cancellation and cleanup
   - Payment idempotency
   - Observability and monitoring queries
   - Database integrity checks

2. **`test_api_endpoints_comprehensive.py`** - API endpoint testing
   - All REST endpoints (start, cancel, approve, status, health)
   - Error conditions and edge cases
   - Temporal integration mocking
   - Concurrency and race conditions
   - Performance characteristics

3. **`test_cli_comprehensive.py`** - Interactive CLI testing
   - Menu navigation and user input
   - Order operations (start, cancel, approve, status)
   - New retry count display functionality
   - Simplified audit logs
   - Address update functionality
   - Error handling and resilience

4. **`test_system_integration.py`** - Cross-component integration
   - API + Workers + Database integration
   - Signal handling between components
   - State consistency across system
   - Health monitoring under load

5. **`test_stress_and_chaos.py`** - Stress testing and chaos engineering
   - High failure rate scenarios
   - Concurrent operations stress testing
   - Resource exhaustion simulation
   - Database connection interruptions
   - Memory pressure testing
   - Extreme retry scenarios

## Running Tests

### Quick Test (Fast Mode)
```bash
python tests/run_comprehensive_tests.py --fast
```
Skips stress tests for faster feedback during development.

### Full Test Suite
```bash
python tests/run_comprehensive_tests.py
```
Runs all tests including stress and chaos engineering.

### Stress Tests Only
```bash
python tests/run_comprehensive_tests.py --stress
```
Runs only stress tests and chaos engineering scenarios.

### Generate HTML Report
```bash
python tests/run_comprehensive_tests.py --report
```
Generates a detailed HTML report with test results.

### Individual Test Suites
```bash
# Run specific test file
pytest tests/test_e2e_workflow_integration.py -v

# Run with output
pytest tests/test_stress_and_chaos.py -v -s
```

## Test Categories

### 🟢 Foundation Tests
- Database connection and queries
- Activity logic (without Temporal SDK)
- Basic CRUD operations

### 🟡 Integration Tests  
- API endpoint functionality
- CLI user interface
- Cross-component communication
- Workflow state management

### 🔴 Stress Tests
- High concurrency scenarios
- Failure rate simulation
- Resource exhaustion
- Chaos engineering

## Key Test Scenarios

### Happy Path Testing
- Complete order flow: creation → validation → approval → payment → shipping
- All database operations succeed
- No retries needed
- Clean state transitions

### Failure Recovery Testing
- Activity failures and retries
- Payment processing errors
- Shipping delays and failures
- System recovery after failures

### Edge Case Testing
- Invalid inputs and malformed data
- Concurrent operations on same order
- Network interruptions
- Database connection issues

### Performance Testing
- Bulk order creation (50+ orders)
- Large event payloads
- Query performance with large datasets
- Memory usage under load

### Chaos Engineering
- Random failures injection
- Connection interruptions
- Resource exhaustion
- Data corruption scenarios

## Expected Results

### Success Criteria
- **Foundation Tests**: 100% pass rate (critical)
- **Integration Tests**: 95%+ pass rate
- **Stress Tests**: 80%+ pass rate (some failures expected)

### Performance Benchmarks
- Order creation: <200ms per order
- Database queries: <1s for recent data
- Bulk operations: <10s for 50 orders
- Observability queries: <5s with large datasets

### Retry Resilience
- Activities should succeed within 10 attempts
- Payment idempotency maintained under retries
- Database consistency preserved during failures

## Troubleshooting

### Architecture Mismatch Errors
If you see `ImportError: dlopen(...) incompatible architecture`, the tests are designed to work around this by:
- Using database-only tests that don't import Temporal SDK
- Mocking Temporal components in API tests
- Focusing on logic validation rather than Temporal integration

### Database Connection Issues
- Ensure PostgreSQL is running: `docker-compose up -d postgres`
- Check connection settings in `db/connection.py`
- Verify database schema is up to date

### Test Data Cleanup
Tests automatically clean up their data, but if needed:
```sql
-- Clean all test data
DELETE FROM activity_attempts WHERE order_id LIKE '%test%';
DELETE FROM events WHERE order_id LIKE '%test%';  
DELETE FROM payments WHERE order_id LIKE '%test%';
DELETE FROM orders WHERE id LIKE '%test%';
```

## Test Data Patterns

Tests use specific naming patterns for easy identification:
- `e2e_*` - End-to-end test data
- `stress_*` - Stress test data  
- `chaos_*` - Chaos engineering data
- `integration_*` - Integration test data
- `*_test` - General test data

## Extending Tests

### Adding New Test Cases
1. Choose appropriate test file based on category
2. Follow existing naming conventions
3. Include proper setup/cleanup
4. Add descriptive docstrings
5. Test both success and failure paths

### Adding New Test Files
1. Follow naming pattern: `test_[category]_[description].py`
2. Add to `run_comprehensive_tests.py` test suite list
3. Include in this README
4. Ensure proper cleanup of test data

## CI/CD Integration

This test suite is designed for CI/CD integration:
- Exit codes indicate overall success/failure
- HTML reports for detailed analysis
- Configurable test depth (fast vs full)
- Timeout protection for long-running tests