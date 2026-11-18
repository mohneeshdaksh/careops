import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from pathways.ivf.workflows import CycleWorkflow

async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="careops",
        workflows=[CycleWorkflow]
    )
    print("Worker running. Press Ctrl+C to stop.")
    await worker.run()

asyncio.run(main())