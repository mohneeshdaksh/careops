from anthropic import AsyncAnthropic
from temporalio import activity

from pathways.ivf.models import LabResult, LabSummary

MODEL = "claude-haiku-5-5"

SYSTEM_PROMPT = (
    "You summarize synthetic IVF lab results for a fertility doctor. "
    "Describe the values factually and briefly. "
    "Never recommend doses, treatment changes, or diagnoses. "
    "The doctor makes all clinical decisions."
)


@activity.defn
async def summarize_labs(labs: list[LabResult]) -> LabSummary:
    lab_lines = "\n".join(f"- {lab.test_name}: {lab.value} {lab.unit}" for lab in labs)

    client = AsyncAnthropic(max_retries=0)
    response = await client.messages.parse(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Summarize these lab results:\n{lab_lines}"}],
        output_format=LabSummary,
    )

    if response.parsed_output is None:
        raise ValueError(f"No valid summary returned (stop_reason: {response.stop_reason})")
    return response.parsed_output
