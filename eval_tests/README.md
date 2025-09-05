# Temporal Workflow - Evaluator Test Suite

This test suite is designed for evaluators to quickly validate the Temporal workflow system.

## 📋 Test Suites Overview

This suite includes three comprehensive test categories:

1. **Temporal Concept Tests** - Core workflow functionality
2. **CLI Logic Tests** - Command-line interface validation  
3. **API Endpoint Tests** - RESTful API verification

## 🎯 What These Tests Cover
### 1. Temporal Concepts Tests (`test_temporal_concepts.py`)

- ✅ Workflow timeout configurations
- ✅ Retry policy logic
- ✅ Signal handling concepts
- ✅ Child workflow orchestration
- ✅ Activity idempotency patterns
- ✅ State transition validation
- ✅ Failure recovery scenarios
- ✅ Manual review SLA logic

### 2. CLI Logic Tests (`test_cli_functionality.py`)

- ✅ Address validation logic
- ✅ Order ID generation
- ✅ CLI menu structure
- ✅ Color formatting functions
- ✅ Print utility functions

### 3. API Endpoint Tests (`test_api_endpoints.py`)

- ✅ Health check endpoint
- ✅ Start order workflow
- ✅ Check order status  
- ✅ Cancel order (signal)
- ✅ Approve order (signal)
- ✅ Complete order flow end-to-end



## 🚀 Setup for Evaluators

```bash
# 1. Create Virtual Environment
python3 -m venv .venv

# 2. Activate Virtual Environment
source .venv/bin/activate

# 3. Install Requirements
pip3 install -r requirements.txt

# 4. Start all services
docker compose down
docker compose -f docker-compose.yml up -d --build
```

Now you're ready to test!

1. Navigate to eval_tests:
   ```bash
   cd eval_tests
   ```

2. You can test all at once with:
   ```bash
   python3 run_evaluator_test.py
   ```

3. Or run individual tests with:
   ```bash
   python3 test_temporal_concepts.py
   python3 test_cli_functionality.py
   python3 test_api_endpoints.py
   ```

## 🔧 Troubleshooting

**If tests fail:**

1. Ensure Docker Compose is running: `docker compose ps`
2. Check API server: `curl http://localhost:8000/health`
3. Verify workers are running: `ps aux | grep python`

## 📊 Expected Results

**All tests should pass** when the system is properly configured, demonstrating:

- Temporal workflow orchestration works correctly
- API endpoints handle requests properly  
- CLI logic functions as expected
- Error handling and retries work as designed
- The system can handle real-world failure scenarios