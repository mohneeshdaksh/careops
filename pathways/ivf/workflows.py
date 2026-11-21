from datetime import timedelta

from temporalio import workflow

from pathways.ivf.models import LabResult


STAGES = ["baseline", "stimulation", "monitoring", "trigger", "retrieval"]


@workflow.defn
class CycleWorkflow:
    def __init__(self) -> None:
        self.stage = "not_started"
        self.labs: list[LabResult] = []

    @workflow.signal
    def add_lab_result(self, lab: LabResult) -> None:
        self.labs.append(lab)

    @workflow.run
    async def run(self, patient_id: str) -> str:
        for stage in STAGES:
            self.stage = stage
            if stage == "monitoring":
                await workflow.wait_condition(lambda: len(self.labs) > 0)
            else:
                await workflow.sleep(timedelta(seconds=10))
        return f"Cycle complete for {patient_id}"