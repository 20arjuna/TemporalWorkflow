import asyncio
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity

# ----- Activity -----
@activity.defn
async def hello_activity(name: str) -> str:
    return f"hello {name}"

# ----- Workflow -----
@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        # Call the activity with a small timeout so this never hangs
        result = await workflow.execute_activity(
            hello_activity,
            name,
            start_to_close_timeout=timedelta(seconds=5),
        )
        return result

# ----- Worker main -----
async def main():
    # Connect to the dev server started by docker-compose
    client = await Client.connect("localhost:7233")
    # Start a worker on a dedicated test queue
    worker = Worker(
        client,
        task_queue="hello-tq",
        workflows=[HelloWorkflow],
        activities=[hello_activity],
    )
    print("✅ Hello worker started on task queue: hello-tq. Press Ctrl+C to stop.")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())