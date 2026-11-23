# CareOps — Clinical Workflow Orchestrator

> **Status: in progress.** First use case: IVF stimulation cycles. Synthetic data only.

CareOps runs long, crash-safe clinical workflows. Lab results arrive as events. AI summarizes them, deterministic rules check them for red flags, and **a clinician approves before the workflow moves on**.

## Why

Clinics run a lot of multi-day workflows by hand: tracking where each patient is in a cycle, chasing lab results, summarizing them for the doctor, and making sure nothing is missed. These workflows wait days for events, must survive restarts, and include steps that need a human decision.

CareOps automates the busywork and keeps the clinical decision with a human:

- **The workflow engine** (Temporal) owns state, timers and retries. It's plain deterministic code.
- **The LLM** (Claude) does only language work: it summarizes lab results.
- **Tracing** (Langfuse) records every LLM call so its input, output, latency and cost can be inspected.
- **Deterministic rules** flag risky values, whatever the LLM says.
- **The doctor** approves or rejects. Nothing clinical happens without them.
- **The audit log** (PostgreSQL) records every event and decision: who did what, to which cycle, and when.

## Architecture

```
                 webhook (lab result)
  Coordinator ──► ┌──────────────┐
  / Doctor        │   FastAPI    │
                  └──────┬───────┘
                         │ start / signal / query / update
                  ┌──────▼───────┐   activity    ┌─────────────────────┐
                  │   Temporal   │ ────────────► │ Claude lab summary  │
                  │CycleWorkflow │               │ (Pydantic-validated)│
                  └──────┬───────┘               └──────────┬──────────┘
                         │ activity                         │ traces
                  ┌──────▼───────┐                     ┌────▼─────┐
                  │  PostgreSQL  │                     │ Langfuse │
                  │  audit log   │                     └──────────┘
                  └──────────────┘

  Red-flag rules run inside the workflow itself (pure, deterministic Python).
```

**IVF cycle stages:** `baseline → stimulation → monitoring → trigger → retrieval`

### How a cycle runs

1. A coordinator starts a cycle (`POST /cycles`). This starts a Temporal `CycleWorkflow` with ID `cycle-{patient_id}`.
2. The workflow moves through the stages on durable timers.
3. At `monitoring`, it waits until a lab result arrives (`POST /cycles/{id}/labs`). The API delivers it as a Temporal **signal**.
4. **Red-flag rules** check the labs (for example, very high estradiol). They're hard-coded thresholds, not AI.
5. A Temporal **activity** asks Claude for a structured summary, validated against a Pydantic model. Retries are capped, and auth or bad-request errors aren't retried.
6. The workflow pauses at `awaiting_approval`. The doctor approves or rejects through a Temporal **Update** (`POST /cycles/{id}/review`). A validator rejects the review if:
   - the cycle isn't awaiting approval yet, or
   - there are red flags and the approval has no note.
7. If approved, the cycle continues to retrieval. If rejected, it's cancelled.
8. Every step above is written to a PostgreSQL **audit log** by a Temporal activity. If the database is down, the workflow waits and retries, so nothing happens without a record.

You can read the current state at any time (`GET /cycles/{id}`) through a Temporal **query**.

## What works today

- [x] Start a cycle over REST. A duplicate start returns `409`.
- [x] Lab-result webhook → workflow signal. An unknown patient returns `404`.
- [x] Live status via workflow query: stage, labs, summary, red flags, review.
- [x] Claude lab summary as a Temporal activity, with structured output and capped retries.
- [x] **Graceful degradation:** if the AI fails, the cycle still goes to the doctor, marked `summary_failed`.
- [x] Deterministic red-flag rules with unit tests. A value in an unexpected unit is flagged as "could not check", not passed silently.
- [x] Doctor review (HITL) as a Temporal Update with validation. Early or invalid reviews are rejected with `409`.
- [x] Approving a flagged cycle requires a written note.
- [x] Langfuse tracing on the summary step: prompt, structured output, latency, tokens and cost per call.
- [x] PostgreSQL audit log: every stage, lab, red-flag check, AI summary, doctor decision (with reviewer and note) and outcome, written by a Temporal activity with parameterized SQL.
- [x] Crash recovery: kill the worker mid-cycle, restart it, and the cycle resumes where it stopped.

Example audit trail for one cycle (trimmed):

```
event_type        | actor       | details
------------------+-------------+-------------------------------------------------
cycle_started     | system      | {"patient_id": "patient-090"}
labs_received     | lab-webhook | {"labs": [{"test_name": "estradiol", "value": 5000.0, ...}]}
red_flags_checked | system      | {"flags": ["very high estradiol ... (limit 4000)"]}
summary_created   | ai          | {"summary": "Estradiol level reported at 5000.0 pg/mL ...", ...}
review_submitted  | dr-smith    | {"decision": "approve", "note": "Reviewed E2, rechecking tomorrow"}
cycle_completed   | system      | {}
```

## Safety principles

- **The system never decides doses or anything medical.** It tracks, summarizes and asks the doctor.
- **Red-flag rules are deterministic** and run independently of the LLM, so a wrong summary can't hide a flag.
- **The LLM only does language work.** Scheduling, state and timers are plain code.
- **Minimum necessary data in prompts:** the LLM sees lab values, not patient identifiers.
- **Synthetic data only.** No real PHI. Thresholds in `red_flags.py` are illustrative, not clinical guidance.
- Secrets live in environment variables (`.env`, never committed).

## Tech stack

| Area | Tool |
|---|---|
| Workflow engine | Temporal (Python SDK) |
| API | FastAPI |
| LLM | Claude API (`anthropic` SDK), structured output via Pydantic |
| Tracing | Langfuse |
| Database | PostgreSQL 17 (Docker), `psycopg` 3 (async), JSONB |
| Validation | Pydantic, dataclasses |
| Tests | pytest |

## Project layout

```
api/main.py                 REST endpoints (start, labs webhook, status, review)
worker.py                   Temporal worker (runs workflows and activities)
pathways/ivf/workflows.py   CycleWorkflow: stages, timers, signal, query, update
pathways/ivf/activities.py  Claude lab-summary activity
pathways/ivf/red_flags.py   Deterministic red-flag rules
pathways/ivf/models.py      LabResult, DoctorReview, LabSummary
engine/audit.py             Audit-log activity (generic, shared by all pathways)
db/schema.sql               audit_events table and index
docker-compose.yml          PostgreSQL container
tests/                      Unit tests
playground/                 Learning code, not part of the app
```

The engine (workflow runner, approvals, AI steps, audit log) is meant to stay generic. Domain details (stages, lab types, thresholds) live in `pathways/ivf/`, so another care pathway can be added alongside it.

## Run it locally

**Requirements:** Python 3.11+, Docker, the [Temporal CLI](https://docs.temporal.io/cli), an Anthropic API key, and (optional) a [Langfuse](https://langfuse.com) project for tracing.

```bash
# 1. Install
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# 2. Add your keys to a .env file (never committed)
cat > .env <<'ENV'
ANTHROPIC_API_KEY=your-key-here
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
POSTGRES_USER=careops
POSTGRES_PASSWORD=choose-a-password
POSTGRES_DB=careops
DATABASE_URL=postgresql://careops:choose-a-password@localhost:5432/careops
ENV

# 3. Start PostgreSQL and create the audit table
docker compose up -d
docker compose exec -T postgres psql -U careops -d careops < db/schema.sql

# 4. Start Temporal (terminal 1). Web UI: http://localhost:8233
temporal server start-dev

# 5. Start the worker (terminal 2)
python worker.py

# 6. Start the API (terminal 3). Docs: http://localhost:8000/docs
python -m uvicorn api.main:app --reload
```

### Try a cycle

```bash
# Start a cycle
curl -X POST localhost:8000/cycles \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "patient-001"}'

# Send a lab result (a high value, so it triggers a red flag)
curl -X POST localhost:8000/cycles/patient-001/labs \
  -H "Content-Type: application/json" \
  -d '{"test_name": "estradiol", "value": 5000, "unit": "pg/mL"}'

# Check status: summary, red flags, stage
curl localhost:8000/cycles/patient-001

# Approve without a note (rejected with 409 because of the red flag)
curl -X POST localhost:8000/cycles/patient-001/review \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve", "reviewer": "dr-smith"}'

# Approve with a note (accepted)
curl -X POST localhost:8000/cycles/patient-001/review \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve", "reviewer": "dr-smith", "note": "Reviewed E2, rechecking tomorrow"}'
```

Stage timers are 10 seconds so a full cycle can be watched in the Temporal UI.

See the cycle's audit trail:

```bash
docker compose exec postgres psql -U careops -d careops -c \
  "SELECT occurred_at, event_type, actor, details FROM audit_events
   WHERE workflow_id = 'cycle-patient-001' ORDER BY occurred_at;"
```

### Run tests

```bash
python -m pytest
```

## Known limitations

- Red flags are checked once, when the first lab arrives. A lab that arrives during the AI summary isn't re-checked or summarized yet.
- The Temporal dev server keeps history in memory. Restarting it loses all cycles.
- No authentication or role-based access on the API yet.
- Blocked review attempts (e.g. approving a flagged cycle without a note) are rejected but not yet written to the audit log.
- The audit log is append-only by convention; the database doesn't yet enforce it (e.g. by revoking `UPDATE`/`DELETE`).
- Each audit write opens a new database connection. A connection pool would be needed at higher volume.
- The schema is a plain SQL file. A migration tool (e.g. Alembic) would be needed as it grows.

## Roadmap

- "Edit" option in doctor review
- Synthetic patients via Synthea and FHIR resources (HAPI FHIR sandbox as mock EHR)
- LangGraph agent for lab triage inside one activity
- RAG over patient-education docs for drafting patient messages
- Streamlit review queue for doctors
- DeepEval suite: summary accuracy, hallucination, red-flag recall

## License

[MIT](LICENSE)
