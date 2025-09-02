import pytest
from activities import stubs
from activities import order_activities, shipping_activities

@pytest.mark.asyncio
async def test_receive_order_calls_stub(monkeypatch):
    async def fake_stub(order_id: str): return {"order_id": order_id}
    monkeypatch.setattr(stubs, "order_received", fake_stub)

    result = await order_activities.receive_order("O-123")
    assert result["order_id"] == "O-123"

@pytest.mark.asyncio
async def test_prepare_package_calls_stub(monkeypatch):
    async def fake_stub(order: dict): return "Package ready"
    monkeypatch.setattr(stubs, "package_prepared", fake_stub)

    result = await shipping_activities.prepare_package({"order_id": "O-123"})
    assert result == "Package ready"
