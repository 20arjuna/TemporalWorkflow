import pytest
import asyncio
from activities import stubs

@pytest.mark.asyncio
async def test_order_received_success(monkeypatch):
    # monkeypatch flaky_call so it doesn't raise or sleep
    async def fake_flaky(): return None
    monkeypatch.setattr(stubs, "flaky_call", fake_flaky)

    result = await stubs.order_received("O-123")
    assert result["order_id"] == "O-123"
    assert "items" in result

@pytest.mark.asyncio
async def test_order_validated_success(monkeypatch):
    async def fake_flaky(): return None
    monkeypatch.setattr(stubs, "flaky_call", fake_flaky)

    order = {"items": [{"sku": "ABC", "qty": 1}]}
    ok = await stubs.order_validated(order)
    assert ok is True
