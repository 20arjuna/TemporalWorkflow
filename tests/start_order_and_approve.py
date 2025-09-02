import asyncio
from temporalio.client import Client
import sys
import os

# Add parent directory to Python path so we can import workflows and activities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows.order_workflow import OrderWorkflow

async def main():
    client = await Client.connect("localhost:7233")

    # Start the workflow but don't wait for it to finish yet
    handle = await client.start_workflow(
        OrderWorkflow.run,
        args=["O-456", {"line1": "123 Maple Ave", "city": "Lincoln", "zip": "68508"}],
        id="order-O-456",
        task_queue="orders-tq",
    )
    print(f"🚀 Workflow started with id={handle.id}")

    # Approve after 1s (within the 3s review window)
    await asyncio.sleep(1)
    await handle.signal(OrderWorkflow.approve)
    print("✅ Sent approve signal")

    # Wait for it to complete
    result = await handle.result()
    print("🎉 Workflow result:", result)

if __name__ == "__main__":
    asyncio.run(main())
