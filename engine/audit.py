import os
from dataclasses import dataclass, field

import psycopg
from psycopg.types.json import Jsonb
from temporalio import activity


@dataclass
class AuditEvent:
    workflow_id: str
    event_type: str
    actor: str
    details: dict = field(default_factory=dict)


@activity.defn
async def record_audit_event(event: AuditEvent) -> None:
    async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
        await conn.execute(
            "INSERT INTO audit_events (workflow_id, event_type, actor, details) "
            "VALUES (%s, %s, %s, %s)",
            (event.workflow_id, event.event_type, event.actor, Jsonb(event.details)),
        )