from datetime import timedelta

from temporalio import workflow

STAGES = ["baseline", "stimulation", "monitoring", "trigger", "retrieval"]


@workflow.defn
class CycleWorkflow:
    @workflow.run
    async def run(self, patient_id: str) -> str:
        for stage in STAGES:
            await workflow.sleep(timedelta(seconds=10))
        return f"Cycle complete for {patient_id}"