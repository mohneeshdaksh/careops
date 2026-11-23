from datetime import timedelta
from dataclasses import asdict

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from pathways.ivf.activities import summarize_labs
    from pathways.ivf.models import LabResult, DoctorReview, LabSummary
    from pathways.ivf.red_flags import check_red_flags
    from engine.audit import AuditEvent, record_audit_event


STAGES = ["baseline", "stimulation", "monitoring", "trigger", "retrieval"]


@workflow.defn
class CycleWorkflow:
    def __init__(self) -> None:
        self.stage = "not_started"
        self.labs: list[LabResult] = []
        self.review: DoctorReview | None = None
        self.summary: LabSummary | None = None
        self.summary_failed = False
        self.red_flags: list[str] = []

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
        if self.red_flags and review.decision == "approve" and not review.note.strip():
            raise ValueError(f"Approval requires a note because of red flags: {self.red_flags}")

    @workflow.query
    def get_status(self) -> dict:
        return {
            "stage": self.stage,
            "labs": self.labs,
            "review": self.review,
            "summary": self.summary,
            "summary_failed": self.summary_failed,
            "red_flags": self.red_flags,
        }

    async def audit(self, event_type: str, actor: str, details: dict | None = None) -> None:
        await workflow.execute_activity(
            record_audit_event,
            AuditEvent(workflow.info().workflow_id, event_type, actor, details or {}),
            start_to_close_timeout=timedelta(seconds=10),
        )

    @workflow.run
    async def run(self, patient_id: str) -> str:
        await self.audit("cycle_started", "system", {"patient_id": patient_id})
        for stage in STAGES:
            self.stage = stage
            await self.audit("stage_started", "system", {"stage": stage})
            if stage == "monitoring":
                await workflow.wait_condition(lambda: len(self.labs) > 0)
                await self.audit("labs_received", "lab-webhook", {"labs": [asdict(lab) for lab in self.labs]})
                self.red_flags = check_red_flags(self.labs)
                await self.audit("red_flags_checked", "system", {"flags": self.red_flags})
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
                if self.summary:
                    await self.audit("summary_created", "ai", self.summary.model_dump())
                else:
                    await self.audit("summary_failed", "ai")
                self.stage = "awaiting_approval"
                await workflow.wait_condition(lambda: self.review is not None)
                await self.audit("review_submitted", self.review.reviewer, {"decision": self.review.decision, "note": self.review.note})
                if self.review.decision == "reject":
                    self.stage = "cancelled"
                    await self.audit("cycle_cancelled", "system")
                    return f"Cycle cancelled for {patient_id} by {self.review.reviewer}: {self.review.note}"
            else:
                await workflow.sleep(timedelta(seconds=10))
        self.stage = "completed"
        await self.audit("cycle_completed", "system")
        return f"Cycle complete for {patient_id}"