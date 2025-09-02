import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_start_endpoint_exists():
    resp = client.post("/orders/O-123/start")
    assert resp.status_code == 501
    assert resp.json()["detail"] == "Not implemented"

def test_cancel_endpoint_exists():
    resp = client.post("/orders/O-123/signals/cancel")
    assert resp.status_code == 501
    assert resp.json()["detail"] == "Not implemented"

def test_status_endpoint_exists():
    resp = client.get("/orders/O-123/status")
    assert resp.status_code == 501
    assert resp.json()["detail"] == "Not implemented"
