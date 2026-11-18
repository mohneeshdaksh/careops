import asyncio

from temporalio.client import Client

from pathways.ivf.workflows import CycleWorkflow


async def main():
    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        CycleWorkflow.run,
        "patient-001",
        id="cycle-patient-001",
        task_queue="careops"
    )
    print(result)

asyncio.run(main())