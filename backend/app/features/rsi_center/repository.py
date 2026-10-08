from app.platform.persistence.orm_models import RSIIterationRecord
from app.platform.persistence.payload_store import dump_payload, load_payload, session_scope


def save_iteration(payload):
    with session_scope() as session:
        session.add(RSIIterationRecord(iteration_id=payload["iteration_id"],
                                       experiment_id=payload["experiment_id"],
                                       status=payload["status"],
                                       payload_json=dump_payload(payload)))


def get_iteration(iteration_id):
    with session_scope() as session:
        record = session.get(RSIIterationRecord, iteration_id)
        return load_payload(record.payload_json) if record else None


def update_iteration(iteration_id, payload):
    with session_scope() as session:
        record = session.get(RSIIterationRecord, iteration_id)
        if record is None:
            return None
        record.status = payload["status"]
        record.payload_json = dump_payload(payload)
        return payload
