from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from temporalio.client import Client, WorkflowFailureError
import sys
import os

# Add parent directory to Python path so we can import workflows
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workflows.order_workflow import OrderWorkflow

app = FastAPI(title="Trellis Takehome API")

# Request models
class StartOrderRequest(BaseModel):
    address: dict

# Temporal client - initialized on startup
temporal_client = None

@app.on_event("startup")
async def startup():
    global temporal_client
    temporal_client = await Client.connect("localhost:7233")

@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify the API is running.
    """
    return {"status": "healthy", "message": "API is running"}

@app.post("/orders/{order_id}/start")
async def start_order(order_id: str, request: StartOrderRequest):
    """
    Start an order workflow.
    """
    try:
        handle = await temporal_client.start_workflow(
            OrderWorkflow.run,
            args=[order_id, request.address],
            id=f"order-{order_id}",
            task_queue="orders-tq",
        )
        return {
            "status": "started",
            "order_id": order_id,
            "workflow_id": handle.id,
            "workflow_run_id": handle.result_run_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")

@app.post("/orders/{order_id}/signals/cancel")
async def cancel_order(order_id: str):
    """
    Cancel a running order workflow.
    """
    try:
        handle = temporal_client.get_workflow_handle(f"order-{order_id}")
        await handle.signal(OrderWorkflow.cancel_order)
        return {
            "status": "cancel_signal_sent",
            "order_id": order_id,
            "workflow_id": f"order-{order_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel workflow: {str(e)}")

@app.get("/orders/{order_id}/status")
async def get_status(order_id: str):
    """
    Get the current status of an order.
    """
    try:
        handle = temporal_client.get_workflow_handle(f"order-{order_id}")
        try:
            # Try to get the result (non-blocking check)
            result = await handle.result(timeout=0.1)
            return {
                "status": "completed", 
                "order_id": order_id,
                "result": result
            }
        except:
            # Workflow is still running
            description = await handle.describe()
            return {
                "status": "running",
                "order_id": order_id,
                "workflow_id": handle.id,
                "run_id": description.run_id,
                "workflow_status": description.status.name
            }
    except Exception as e:
        return {
            "status": "not_found",
            "order_id": order_id,
            "error": str(e)
        }

@app.post("/orders/{order_id}/signals/approve")
async def approve_order(order_id: str):
    """
    Send approve signal to order workflow.
    """
    try:
        handle = temporal_client.get_workflow_handle(f"order-{order_id}")
        await handle.signal(OrderWorkflow.approve)
        return {
            "status": "approve_signal_sent",
            "order_id": order_id,
            "workflow_id": f"order-{order_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve workflow: {str(e)}")
