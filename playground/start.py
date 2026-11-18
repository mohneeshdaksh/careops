import asyncio

from temporalio.client import Client

from hello import HelloWorkflow


async def main():
    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        HelloWorkflow.run,
        "Mohneesh",
        id="hello-1",
        task_queue="hello-queue",
    )
    print(result)


asyncio.run(main())