from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from pathways.ivf.workflows import CycleWorkflow


class StartCycleRequest(BaseModel):
    patient_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.temporal = await Client.connect("localhost:7233")
    yield


app = FastAPI(title="CareOps", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/cycles", status_code=202)
async def start_cycle(body: StartCycleRequest, request: Request):
    client = request.app.state.temporal
    try:
        handle = await client.start_workflow(
            CycleWorkflow.run,
            body.patient_id,
            id=f"cycle-{body.patient_id}",
            task_queue="careops"
        )
    except WorkflowAlreadyStartedError:
        raise HTTPException(
            status_code=409, 
            detail=f"Cycle already started for patient {body.patient_id}")
    return {"workflow_id": handle.id, "status": "started"}