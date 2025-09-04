"""
Temporal Workflow API Testing - Evaluator Version

Tests the FastAPI endpoints without database imports to avoid architecture issues.
Uses requests to test the actual HTTP API endpoints.

Run with: pip install requests && python -m pytest eval_tests/test_api_endpoints.py -v
"""

import pytest
import requests
import json
import time
from typing import Dict, Any

# API Base URL
BASE_URL = "http://localhost:8000"

class TestTemporalWorkflowAPI:
    """Test the complete Temporal workflow system via API endpoints."""
    
    def test_health_endpoint(self):
        """Test the health check endpoint works."""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✅ Health endpoint working")
    
    def test_start_order_endpoint(self):
        """Test starting an order via API."""
        order_id = "eval_test_001"
        address = {
            "line1": "123 Eval Street", 
            "city": "TestCity", 
            "state": "TC", 
            "zip": "12345"
        }
        
        response = requests.post(
            f"{BASE_URL}/orders/{order_id}/start",
            json={"address": address}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["order_id"] == order_id
        assert "workflow_id" in data
        print(f"✅ Order {order_id} started successfully")
    
    def test_order_status_endpoint(self):
        """Test checking order status via API."""
        order_id = "eval_test_002"
        address = {"line1": "456 Status Ave", "city": "StatusCity", "state": "SC", "zip": "67890"}
        
        # Start order first
        start_response = requests.post(
            f"{BASE_URL}/orders/{order_id}/start",
            json={"address": address}
        )
        assert start_response.status_code == 200
        
        # Check status
        status_response = requests.get(f"{BASE_URL}/orders/{order_id}/status")
        assert status_response.status_code == 200
        
        data = status_response.json()
        assert data["order_id"] == order_id
        assert "status" in data
        assert "workflow_status" in data
        print(f"✅ Order status retrieved: {data['status']}")
    
    def test_cancel_order_endpoint(self):
        """Test canceling an order via API."""
        order_id = "eval_test_cancel"
        address = {"line1": "789 Cancel Blvd", "city": "CancelTown", "state": "CT", "zip": "99999"}
        
        # Start order first
        start_response = requests.post(
            f"{BASE_URL}/orders/{order_id}/start",
            json={"address": address}
        )
        assert start_response.status_code == 200
        
        # Cancel order
        cancel_response = requests.post(f"{BASE_URL}/orders/{order_id}/signals/cancel")
        assert cancel_response.status_code == 200
        
        data = cancel_response.json()
        assert data["status"] == "cancel_signal_sent"
        assert data["order_id"] == order_id
        print(f"✅ Order {order_id} cancelled successfully")
    
    def test_approve_order_endpoint(self):
        """Test approving an order via API."""
        order_id = "eval_test_approve"
        address = {"line1": "321 Approve Lane", "city": "ApproveVille", "state": "AV", "zip": "11111"}
        
        # Start order first
        start_response = requests.post(
            f"{BASE_URL}/orders/{order_id}/start",
            json={"address": address}
        )
        assert start_response.status_code == 200
        
        # Wait a moment for workflow to reach validation
        time.sleep(2)
        
        # Approve order
        approve_response = requests.post(f"{BASE_URL}/orders/{order_id}/signals/approve")
        assert approve_response.status_code == 200
        
        data = approve_response.json()
        assert data["status"] == "approve_signal_sent"
        assert data["order_id"] == order_id
        print(f"✅ Order {order_id} approved successfully")
    
    def test_complete_order_flow_via_api(self):
        """Test complete order flow: start → approve → check final status."""
        order_id = "eval_complete_flow"
        address = {
            "line1": "555 Complete Circle", 
            "city": "FlowCity", 
            "state": "FC", 
            "zip": "55555"
        }
        
        # 1. Start order
        start_response = requests.post(
            f"{BASE_URL}/orders/{order_id}/start",
            json={"address": address}
        )
        assert start_response.status_code == 200
        print(f"✅ Started order {order_id}")
        
        # 2. Wait for validation (orders need to reach "validated" before approval)
        max_wait = 30  # 30 seconds max
        validated = False
        
        for i in range(max_wait):
            status_response = requests.get(f"{BASE_URL}/orders/{order_id}/status")
            if status_response.status_code == 200:
                data = status_response.json()
                if "validated" in data.get("status", "").lower():
                    validated = True
                    print(f"✅ Order reached validation after {i+1}s")
                    break
            time.sleep(1)
        
        if not validated:
            print("⚠️  Order didn't reach validation in 30s, approving anyway")
        
        # 3. Approve order
        approve_response = requests.post(f"{BASE_URL}/orders/{order_id}/signals/approve")
        assert approve_response.status_code == 200
        print(f"✅ Approved order {order_id}")
        
        # 4. Wait for completion or significant progress
        time.sleep(10)
        
        # 5. Check final status
        final_status_response = requests.get(f"{BASE_URL}/orders/{order_id}/status")
        assert final_status_response.status_code == 200
        
        final_data = final_status_response.json()
        print(f"✅ Final order status: {final_data.get('status', 'unknown')}")
        print(f"✅ Workflow status: {final_data.get('workflow_status', 'unknown')}")
        
        # The order should have progressed beyond "received"
        status = final_data.get("status", "").lower()
        assert status != "pending", f"Order should have progressed beyond pending, got: {status}"
        print(f"✅ Complete flow test passed - order progressed to: {status}")

if __name__ == "__main__":
    print("🚀 TEMPORAL WORKFLOW API TESTS")
    print("=" * 50)
    print("Prerequisites:")
    print("Ensure Docker Compose is running")
    print("=" * 50)
    
    # Run a quick connectivity test
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API server is running and reachable")
        else:
            print(f"❌ API server returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Cannot reach API server: {e}")
        print("Please start the API server with: python run_api.py")
        exit(1)
    
    print("\n🧪 Running tests...")