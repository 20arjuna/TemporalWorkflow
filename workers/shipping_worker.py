import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

import sys
import os

# Add parent directory to Python path so we can import workflows and activities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows.shipping_workflow import ShippingWorkflow
from activities.shipping_activities import prepare_package, dispatch_carrier

async def main():
    # client = await Client.connect("localhost:7233")
    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    client = await Client.connect(temporal_host)

    worker = Worker(
        client,
        task_queue="shipping-tq",
        workflows=[ShippingWorkflow],
        activities=[prepare_package, dispatch_carrier],
    )

    print("✅ Shipping worker started on shipping-tq. Waiting for tasks...")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
