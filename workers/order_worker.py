import asyncio
from temporalio.worker import Worker
from temporalio.client import Client
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
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
