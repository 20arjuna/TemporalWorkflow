import asyncio
from temporalio.client import Client
import sys
import os

# Add parent directory to Python path so we can import workflows and activities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows.order_workflow import OrderWorkflow

async def main():
    # connect to temporal dev server
    client = await Client.connect("localhost:7233")

    # kick off the workflow
    result = await client.execute_workflow(
        OrderWorkflow.run,
        args=["O-123", {"line1": "1 Main St", "city": "Omaha", "zip": "68102"}],
        id="order-O-123",               # workflow id
        task_queue="orders-tq",         # parent queue
    )

    print("✅ Workflow result:", result)

if __name__ == "__main__":
    asyncio.run(main())
