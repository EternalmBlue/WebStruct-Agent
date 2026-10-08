"""Persisted local task runtime with domain workflow injection."""
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import uuid4

from app.platform.configuration import settings
from app.platform.persistence.json_payloads import jsonable_state
from app.platform.persistence.orm_models import RuntimeEventRecord, RuntimeTaskRecord
from app.platform.persistence.payload_store import dump_payload, load_payload, session_scope

active_task: ContextVar[str | None] = ContextVar("active_task", default=None)


def now() -> str:
    return datetime.now(UTC).isoformat()


class TaskRuntime:
    def __init__(self) -> None:
        self.lock = RLock()
        self.executor = ThreadPoolExecutor(
            max_workers=settings.max_workers, thread_name_prefix="webstruct"
        )

    def _event(self, session, record, snapshot, event_type, **details):
        snapshot["event_cursor"] += 1
        snapshot["updated_at"] = now()
        event = {
            "task_id": record.task_id,
            "correlation_id": snapshot["correlation_id"],
            "sequence": snapshot["event_cursor"],
            "event_type": event_type,
            "timestamp": snapshot["updated_at"],
            **details,
        }
        session.add(
            RuntimeEventRecord(
                task_id=record.task_id,
                sequence=event["sequence"],
                payload_json=dump_payload(event),
            )
        )
        record.status = snapshot["status"]
        record.payload_json = dump_payload(snapshot)

    def create(
        self,
        kind: str,
        nodes: list[str],
        request: dict | None,
        *,
        correlation_id: str | None = None,
        parent_task_id: str | None = None,
        original_task_id: str | None = None,
    ) -> dict:
        task_id = f"{kind[:7]}-{uuid4().hex}"
        snapshot = {
            "task_id": task_id,
            "correlation_id": correlation_id or uuid4().hex,
            "parent_task_id": parent_task_id,
            "original_task_id": original_task_id,
            "workflow_type": kind,
            "status": "queued",
            "current_node": None,
            "completed_node_count": 0,
            "total_node_count": len(nodes),
            "progress": 0,
            "nodes": {
                name: {
                    "name": name,
                    "status": "pending",
                    "role": "",
                    "start_time": None,
                    "end_time": None,
                    "runtime_ms": None,
                }
                for name in nodes
            },
            "created_at": now(),
            "updated_at": now(),
            "start_time": None,
            "end_time": None,
            "runtime_ms": None,
            "queue_wait_ms": None,
            "event_cursor": 0,
            "errors": [],
            "config_version": settings.config_version,
            "retry_available": request is not None and settings.retain_business_payload,
        }
        with self.lock, session_scope() as session:
            record = RuntimeTaskRecord(
                task_id=task_id,
                kind=kind,
                status="queued",
                payload_json=dump_payload(snapshot),
                request_json=dump_payload(request)
                if snapshot["retry_available"]
                else None,
            )
            session.add(record)
            self._event(session, record, snapshot, "task_queued", status="queued")
        return {
            "task_id": task_id,
            "correlation_id": snapshot["correlation_id"],
            "status": "queued",
        }

    def snapshot(self, task_id: str) -> dict | None:
        with session_scope() as session:
            record = session.get(RuntimeTaskRecord, task_id)
            return load_payload(record.payload_json) if record else None

    def result(self, task_id: str) -> dict | None:
        with session_scope() as session:
            record = session.get(RuntimeTaskRecord, task_id)
            return load_payload(record.result_json) if record and record.result_json else None

    def request(self, task_id: str) -> dict | None:
        with session_scope() as session:
            record = session.get(RuntimeTaskRecord, task_id)
            return load_payload(record.request_json) if record and record.request_json else None

    def retry(self, task_id: str) -> dict:
        """Create a new run from a retained request without mutating the original."""
        with self.lock, session_scope() as session:
            record = session.get(RuntimeTaskRecord, task_id)
            if record is None:
                raise LookupError("run not found")
            snapshot = load_payload(record.payload_json)
            if snapshot["status"] != "failed":
                raise ValueError("only failed runs can be retried")
            request = load_payload(record.request_json) if record.request_json else None
            if request is None:
                raise ValueError("run input was not retained; retry is unavailable")
            kind = record.kind
            nodes = list(snapshot.get("nodes", {}).keys())
            correlation_id = snapshot["correlation_id"]
        receipt = self.create(
            kind,
            nodes,
            request,
            correlation_id=correlation_id,
            original_task_id=task_id,
        )
        return {**receipt, "workflow_type": kind}

    def events(self, task_id: str, after_cursor: int = 0) -> dict:
        with session_scope() as session:
            rows = (
                session.query(RuntimeEventRecord)
                .filter(
                    RuntimeEventRecord.task_id == task_id,
                    RuntimeEventRecord.sequence > after_cursor,
                )
                .order_by(RuntimeEventRecord.sequence)
                .limit(settings.event_page_size)
                .all()
            )
            events = [load_payload(row.payload_json) for row in rows]
            return {
                "events": events,
                "next_cursor": events[-1]["sequence"] if events else after_cursor,
            }

    def start(self, task_id: str) -> None:
        with self.lock, session_scope() as session:
            record = session.get(RuntimeTaskRecord, task_id)
            if not record:
                return
            snapshot = load_payload(record.payload_json)
            if snapshot["status"] != "queued":
                return
            started_at = now()
            snapshot.update(status="running", start_time=started_at,
                            queue_wait_ms=max(0, (datetime.fromisoformat(started_at) -
                                datetime.fromisoformat(snapshot["created_at"])).total_seconds() * 1000))
            self._event(session, record, snapshot, "task_started", status="running")

    def node(
        self,
        task_id: str,
        name: str,
        role: str,
        status: str,
        *,
        runtime_ms: int | None = None,
        input_summary: str = "",
        output_summary: str = "",
        error_message: str | None = None,
    ) -> None:
        with self.lock, session_scope() as session:
            record = session.get(RuntimeTaskRecord, task_id)
            if not record:
                return
            snapshot = load_payload(record.payload_json)
            if snapshot["status"] in {"failed", "completed"} or name not in snapshot["nodes"]:
                return
            node = snapshot["nodes"][name]
            if node["status"] in {"failed", "success", "skipped"}:
                return
            node.update(
                role=role,
                status=status,
                runtime_ms=runtime_ms,
                input_summary=settings.redact(input_summary),
                output_summary=settings.redact(output_summary),
                error_message=settings.redact(error_message)
                if error_message
                else None,
            )
            if status == "running":
                node["start_time"] = now()
                snapshot["current_node"] = name
            else:
                node["end_time"] = now()
                snapshot["current_node"] = None
            snapshot["completed_node_count"] = sum(
                current["status"] in {"success", "skipped"}
                for current in snapshot["nodes"].values()
            )
            snapshot["progress"] = round(
                100 * snapshot["completed_node_count"] / snapshot["total_node_count"], 1
            ) if snapshot["total_node_count"] else 100
            self._event(
                session,
                record,
                snapshot,
                "node_started" if status == "running" else "node_finished",
                **node,
            )

    def decision(self, event_type: str, **details) -> None:
        task_id = active_task.get()
        if not task_id:
            return
        with self.lock, session_scope() as session:
            record = session.get(RuntimeTaskRecord, task_id)
            if not record:
                return
            snapshot = load_payload(record.payload_json)
            if snapshot["status"] in {"failed", "completed"}:
                return
            from app.platform.observability.telemetry import redact_tree
            safe = redact_tree(details)
            self._event(session, record, snapshot, event_type, **safe)

    def finish(self, task_id: str, state: dict, elapsed_ms: int) -> None:
        status = "failed" if state.get("status") == "failed" else "completed"
        snapshot = self.snapshot(task_id)
        if not snapshot:
            return
        from app.platform.observability.metrics import build_run_metrics, metric
        with session_scope() as session:
            observations = [load_payload(row.payload_json) for row in session.query(RuntimeEventRecord)
                            .filter(RuntimeEventRecord.task_id == task_id).order_by(RuntimeEventRecord.sequence)]
        try:
            measurements = build_run_metrics(state, elapsed_ms, observations)
        except Exception as exc:
            measurements = {"metrics_version": "2", "metrics": {},
                            "fingerprint": {}, "metrics_error": settings.redact(str(exc))}
        measurements["metrics"]["queue_wait_ms"] = metric(snapshot.get("queue_wait_ms"), unit="ms")
        for name, node in snapshot["nodes"].items():
            if node["status"] in {"pending", "running"}:
                self.node(
                    task_id,
                    name,
                    node["role"],
                    "skipped",
                    output_summary="upstream failure" if status == "failed" else "not required",
                )
        with self.lock, session_scope() as session:
            record = session.get(RuntimeTaskRecord, task_id)
            if not record:
                return
            snapshot = load_payload(record.payload_json)
            if snapshot["status"] in {"failed", "completed"}:
                return
            snapshot.update(
                status=status,
                current_node=None,
                end_time=now(),
                runtime_ms=elapsed_ms,
                errors=[settings.redact(error) for error in state.get("errors", [])],
                **measurements,
            )
            result = jsonable_state(
                {
                    **state,
                    "status": status,
                    "task_id": task_id,
                    "correlation_id": snapshot["correlation_id"],
                }
            )
            result["errors"] = snapshot["errors"]
            result.update(measurements)
            if not settings.retain_business_payload:
                for key in ("input_html", "page_observation", "view_bundle", "benchmark_dataset"):
                    result.pop(key, None)
            record.result_json = dump_payload(result)
            self._event(
                session,
                record,
                snapshot,
                "task_finished",
                status=status,
                runtime_ms=elapsed_ms,
                errors=snapshot["errors"],
            )

    def execute(self, task_id: str, workflow) -> None:
        token = active_task.set(task_id)
        started = time.perf_counter()
        try:
            self.start(task_id)
            state = workflow(task_id)
        except Exception as exc:
            state = {"status": "failed", "errors": [settings.redact(str(exc))]}
        try:
            self.finish(task_id, state, int((time.perf_counter() - started) * 1000))
        finally:
            active_task.reset(token)

    def submit(self, receipt: dict, workflow) -> None:
        self.executor.submit(self.execute, receipt["task_id"], workflow)

    def recover_interrupted(self) -> None:
        with session_scope() as session:
            ids = [
                record.task_id
                for record in session.query(RuntimeTaskRecord)
                .filter(RuntimeTaskRecord.status.in_(["queued", "running"]))
                .all()
            ]
        for task_id in ids:
            self.finish(
                task_id,
                {"status": "failed", "errors": ["backend restart interrupted task"]},
                0,
            )

    def summary(self, hours: int = 24) -> dict:
        since = datetime.now(UTC) - timedelta(hours=hours)
        with session_scope() as session:
            snapshots = [
                load_payload(record.payload_json)
                for record in session.query(RuntimeTaskRecord).all()
            ]
        snapshots = [
            snapshot
            for snapshot in snapshots
            if not snapshot.get("parent_task_id")
            and datetime.fromisoformat(snapshot["created_at"]) >= since
        ]
        from app.platform.observability.metrics import summarize_runs
        return summarize_runs(snapshots)


runtime = TaskRuntime()
