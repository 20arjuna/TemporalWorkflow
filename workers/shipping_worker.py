import asyncio
from temporalio.worker import Worker
from temporalio.client import Client
from workflows.shipping_workflow import ShippingWorkflow
from activities.shipping_activities import prepare_package, dispatch_carrier

async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="shipping-tq",
        workflows=[ShippingWorkflow],
        activities=[prepare_package, dispatch_carrier],
    )
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
