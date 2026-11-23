import asyncio

from dotenv import load_dotenv

load_dotenv()

from engine.audit import AuditEvent, record_audit_event

asyncio.run(record_audit_event(AuditEvent(
    workflow_id="cycle-test",
    event_type="test_event",
    actor="playground",
    details={"hello": "world"},
)))
print("inserted")