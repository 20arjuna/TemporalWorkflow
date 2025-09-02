from fastapi import FastAPI, HTTPException

app = FastAPI(title="Trellis Takehome API")

@app.post("/orders/{order_id}/start")
async def start_order(order_id: str):
    """
    Start an order workflow.
    For now this just returns 501.
    """
    raise HTTPException(status_code=501, detail="Not implemented")

@app.post("/orders/{order_id}/signals/cancel")
async def cancel_order(order_id: str):
    """
    Cancel a running order workflow.
    """
    raise HTTPException(status_code=501, detail="Not implemented")

@app.get("/orders/{order_id}/status")
async def get_status(order_id: str):
    """
    Get the current status of an order.
    """
    raise HTTPException(status_code=501, detail="Not implemented")
