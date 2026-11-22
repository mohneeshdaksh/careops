from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from pathways.ivf.activities import summarize_labs
    from pathways.ivf.models import LabResult, DoctorReview, LabSummary


STAGES = ["baseline", "stimulation", "monitoring", "trigger", "retrieval"]


@workflow.defn
class CycleWorkflow:
    def __init__(self) -> None:
        self.stage = "not_started"
        self.labs: list[LabResult] = []
        self.review: DoctorReview | None = None
        self.summary: LabSummary | None = None
        self.summary_failed = False

    @workflow.signal
    def add_lab_result(self, lab: LabResult) -> None:
        self.labs.append(lab)

    @workflow.update
    def submit_review(self, review: DoctorReview) -> str:
        self.review = review
        return "review accepted"

    @submit_review.validator
    def validate_review(self, review: DoctorReview) -> None:
        if self.stage != "awaiting_approval":
            raise ValueError(f"Cannot accept a review: cycle is in '{self.stage}', not awaiting approval")

    @workflow.query
    def get_status(self) -> dict:
        return {
            "stage": self.stage,
            "labs": self.labs,
            "review": self.review,
            "summary": self.summary,
            "summary_failed": self.summary_failed,
        }

    @workflow.run
    async def run(self, patient_id: str) -> str:
        for stage in STAGES:
            self.stage = stage
            if stage == "monitoring":
                await workflow.wait_condition(lambda: len(self.labs) > 0)
                try:
                    self.summary = await workflow.execute_activity(
                        summarize_labs,
                        self.labs,
                        start_to_close_timeout=timedelta(seconds=60),
                        retry_policy=RetryPolicy(
                            maximum_attempts=3,
                            non_retryable_error_types=[
                                "AuthenticationError",
                                "PermissionDeniedError",
                                "BadRequestError",
                            ],
                        ),
                    )
                except ActivityError:
                    self.summary = None
                    self.summary_failed = True
                self.stage = "awaiting_approval"
                await workflow.wait_condition(lambda: self.review is not None)
                if self.review.decision == "reject":
                    self.stage = "cancelled"
                    return f"Cycle cancelled for {patient_id} by {self.review.reviewer}: {self.review.note}"
            else:
                await workflow.sleep(timedelta(seconds=10))
        self.stage = "completed"
        return f"Cycle complete for {patient_id}"