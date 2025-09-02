import asyncio
import sys
import os
from temporalio.client import Client
from temporalio.worker import Worker

# Add parent directory to Python path so we can import workflows and activities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# import workflows + activities
from workflows.order_workflow import OrderWorkflow
from activities.order_activities import receive_order, validate_order, charge_payment

async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="orders-tq",
        workflows=[OrderWorkflow],
        activities=[receive_order, validate_order, charge_payment],
    )

    print("✅ Orders worker started on orders-tq. Waiting for tasks...")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())