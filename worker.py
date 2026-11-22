import asyncio

from dotenv import load_dotenv

load_dotenv()

from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.contrib.pydantic import pydantic_data_converter

from pathways.ivf.workflows import CycleWorkflow
from pathways.ivf.activities import summarize_labs


async def main():
    client = await Client.connect("localhost:7233", data_converter=pydantic_data_converter)
    worker = Worker(
        client,
        task_queue="careops",
        workflows=[CycleWorkflow],
        activities=[summarize_labs],
    )
    print("Worker running. Press Ctrl+C to stop.")
    await worker.run()


asyncio.run(main())