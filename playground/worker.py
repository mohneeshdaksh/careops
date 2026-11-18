import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from hello import HelloWorkflow, say_hello

async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="hello-queue",
        workflows=[HelloWorkflow],
        activities=[say_hello],
    )
    print("Worker running. Press Ctrl+C to stop.")
    await worker.run()


asyncio.run(main())