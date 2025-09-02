# save this as scripts/run_hello.py (create scripts/ if you want)
import asyncio
from temporalio.client import Client
from hello_world_worker import HelloWorkflow  # reuse the class we defined

async def main():
    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        HelloWorkflow.run,
        "Temporal",
        id="hello-1",
        task_queue="hello-tq",
    )
    print("Workflow result:", result)

if __name__ == "__main__":
    asyncio.run(main())
