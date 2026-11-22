from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode
from temporalio.client import WorkflowUpdateFailedError

from pathways.ivf.workflows import CycleWorkflow
from pathways.ivf.models import LabResult, DoctorReview


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


@app.post("/cycles/{patient_id}/labs", status_code=202)
async def receive_lab_result(patient_id: str, lab: LabResult, request: Request):
    client = request.app.state.temporal
    handle = client.get_workflow_handle(f"cycle-{patient_id}")
    try:
        await handle.signal(CycleWorkflow.add_lab_result, lab)
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            raise HTTPException(
                status_code=404,
                detail=f"No active cycle found for patient {patient_id}"
            )
        raise
    return {"workflow_id": f"cycle-{patient_id}", "status": "lab result received"}


@app.get("/cycles/{patient_id}")
async def get_cycle_status(patient_id: str, request: Request):
    client = request.app.state.temporal
    handle = client.get_workflow_handle(f"cycle-{patient_id}")
    try:
        status = await handle.query(CycleWorkflow.get_status)
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            raise HTTPException(
                status_code=404,
                detail=f"No active cycle found for patient {patient_id}"
            )
        raise
    return {"workflow_id": f"cycle-{patient_id}", "status": status}


@app.post("/cycles/{patient_id}/review", status_code=200)
async def submit_doctor_review(patient_id: str, review: DoctorReview, request: Request):
    client = request.app.state.temporal
    handle = client.get_workflow_handle(f"cycle-{patient_id}")
    try:
        await handle.execute_update(CycleWorkflow.submit_review, review)
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            raise HTTPException(
                status_code=404,
                detail=f"No active cycle found for patient {patient_id}"
            )
        raise
    except WorkflowUpdateFailedError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e.cause)
        )
    return {"workflow_id": f"cycle-{patient_id}", "status": "doctor review received"}