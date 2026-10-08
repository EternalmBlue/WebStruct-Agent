"""Opt-in fixed-URL MineBBS experiment; never discovers or downloads resources."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.contracts import (
    ExtractionRequest,
    FieldProgramSpec,
    FieldSpec,
    ProgramSpec,
    RSIIterationRequest,
    SchemaSpec,
)
from app.features.extraction_center.workflow import (
    EXTRACTION_NODE_NAMES,
    run_extraction_workflow_for_task,
)
from app.features.page_center.collector import collect_page
from app.features.rsi_center.service import evaluate_iteration
from app.platform.configuration import settings
from app.platform.dom import parse_html, select_values
from app.platform.observability import runtime
from app.platform.observability.telemetry import capture_observations

RESOURCE_URLS = [
    "https://www.minebbs.com/resources/warzrealms.15425/",
    "https://www.minebbs.com/resources/warzsafebox-mc.11399/",
    "https://www.minebbs.com/resources/hanglevel.15596/",
    "https://www.minebbs.com/resources/silencewarden-web-x.18523/",
    "https://www.minebbs.com/resources/suixinjs-x.18522/",
    "https://www.minebbs.com/resources/littlearena-q-bot.18452/",
    "https://www.minebbs.com/resources/yucobbluckymatch.18284/",
    "https://www.minebbs.com/resources/randomdailybroadcast-x-x.18516/",
    "https://www.minebbs.com/resources/webmarket-gui.13231/",
    "https://www.minebbs.com/resources/alcerecipeviewer-craftengine-gui-folia.16778/",
]

SCHEMA = SchemaSpec(
    name="MineBBS Resource Validation",
    domain="forum-resource",
    fields=[
        FieldSpec(name="title", description="Resource title", type="text", required=True),
        FieldSpec(name="version", description="Resource version", type="text", required=False),
        FieldSpec(name="author", description="Author", type="text", required=False),
        FieldSpec(name="body", description="Resource body", type="text", required=False),
    ],
)


REFERENCE_PROGRAM = ProgramSpec(field_programs=[
    FieldProgramSpec(
        field_name="title", strategy="css", selector="h1.p-title-value",
        postprocess=["strip", "normalize_whitespace"],
    ),
    FieldProgramSpec(
        field_name="version", strategy="xpath",
        selector="//h1[contains(@class, 'p-title-value')]//*[contains(@class, 'u-muted')]/text()",
        postprocess=["strip", "normalize_whitespace"],
    ),
    FieldProgramSpec(
        field_name="author", strategy="css", selector=".p-description a.username",
        postprocess=["strip", "normalize_whitespace"],
    ),
    FieldProgramSpec(
        field_name="body", strategy="css", selector=".resourceBody-main .bbWrapper",
        postprocess=["strip", "normalize_whitespace"],
    ),
])


def _run_persisted(request: ExtractionRequest) -> tuple[dict, dict]:
    receipt = runtime.create(
        "extraction",
        EXTRACTION_NODE_NAMES + ["result_persist_node"],
        request.model_dump(mode="json"),
    )
    with capture_observations() as observations:
        runtime.execute(
            receipt["task_id"],
            lambda task_id: run_extraction_workflow_for_task(request, task_id),
        )
    return runtime.snapshot(receipt["task_id"]), {
        "observations": observations,
        "result": runtime.result(receipt["task_id"]) or {},
    }


def run(replay_rows: list[dict] | None = None) -> list[dict[str, object]]:
    rows = []
    sources = {row["url"]: row for row in replay_rows or []}
    for index, url in enumerate(RESOURCE_URLS, start=1):
        try:
            source = sources.get(url)
            if replay_rows is not None and source is None:
                raise ValueError("replay report is missing the fixed URL")
            if source:
                previous = runtime.result(source["baseline_task_id"]) or {}
                page = previous.get("page_observation") or {}
                if not page.get("html"):
                    raise ValueError("page snapshot was not retained; replay is unavailable")
                html, final_url = page["html"], page["url"]
                collection = source["collection"]
                baseline_snapshot = runtime.snapshot(source["baseline_task_id"])
                baseline_state = previous
            else:
                collected = collect_page(target_url=url)
                html, final_url = collected.html, collected.url
                collection = collected.metadata["collection_attempts"][0]
            request = ExtractionRequest(
                target_url=final_url,
                html=html,
                schema_spec=SCHEMA,
                persist_result=False,
            )
            if not source:
                baseline_snapshot, baseline_payload = _run_persisted(request)
                baseline_state = baseline_payload["result"]
            candidate_snapshot, candidate_payload = _run_persisted(
                request.model_copy(update={"program_spec": REFERENCE_PROGRAM}),
            )
            candidate_state = candidate_payload["result"]
            baseline_metrics = baseline_snapshot["metrics"]
            candidate_metrics = candidate_snapshot["metrics"]
            root = parse_html(html)
            dom_references = {}
            for program in REFERENCE_PROGRAM.field_programs:
                if not program.selector:
                    continue
                try:
                    dom_references[program.field_name] = {
                        "selector": program.selector,
                        "values": select_values(
                            root, program.strategy, program.selector, program.attribute
                        ),
                    }
                except Exception as exc:
                    dom_references[program.field_name] = {
                        "selector": program.selector,
                        "error": f"{exc.__class__.__name__}: {exc}",
                    }
            iteration = evaluate_iteration(RSIIterationRequest(
                experiment_id="minebbs-category-70",
                baseline_run_id=baseline_snapshot["task_id"],
                candidate_run_id=candidate_snapshot["task_id"],
                hypothesis_id="reference-selectors",
                hypothesis="Scoped resource selectors improve field completion and evidence.",
                intervention="minebbs_reference_program",
                change_set_id="resource-validation-smoke-v2",
            ))
            result = candidate_state.get("extraction_result") or {}
            fields = result.get("fields", [])
            reference_values = {name: (ref.get("values") or [None])[0]
                                for name, ref in dom_references.items()}
            rows.append({
                "url": url,
                "status": candidate_snapshot.get("status"),
                "collection": collection,
                "collection_replayed": bool(source),
                "quality_basis": "DOM references, not human-labelled accuracy",
                "structure": {
                    "html_chars": len(html),
                    "body_chars": len(reference_values.get("body") or ""),
                    "body_image_count": len(root.cssselect(".resourceBody-main .bbWrapper img")),
                    "body_table_count": len(root.cssselect(".resourceBody-main .bbWrapper table")),
                    "body_code_count": len(root.cssselect(".resourceBody-main .bbWrapper pre")),
                    "reference_match_counts": {
                        name: len(ref.get("values", [])) for name, ref in dom_references.items()
                    },
                },
                "baseline_task_id": baseline_snapshot["task_id"],
                "candidate_task_id": candidate_snapshot["task_id"],
                "rsi_iteration": {
                    "iteration_id": iteration["iteration_id"],
                    "status": iteration["status"],
                    "decision_reason": iteration["decision_reason"],
                    "quality_proxy_delta": iteration["metric_deltas"].get("quality_proxy"),
                },
                "dom_references": dom_references,
                "baseline_metrics": baseline_metrics,
                "candidate_metrics": candidate_metrics,
                "baseline_fields": (baseline_state.get("extraction_result") or {}).get("fields", []),
                "fields": {
                    field["field_name"]: {
                        "value": field.get("normalized_value"),
                        "status": field.get("status"),
                        "has_value": field.get("normalized_value") not in (None, "", []),
                        "evidence_count": len(field.get("evidence", [])),
                        "matches_dom_reference": (
                            field.get("normalized_value") == reference_values[field["field_name"]]
                            if field["field_name"] in reference_values else None
                        ),
                    }
                    for field in fields
                },
                "metrics": candidate_metrics,
            })
        except Exception as exc:
            rows.append({"url": url, "status": "failed",
                         "error": settings.redact(f"{exc.__class__.__name__}: {exc}")})
        print(f"{index}/{len(RESOURCE_URLS)} {url}: {rows[-1]['status']}", file=sys.stderr)
    return rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-report", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    source_rows = (json.loads(arguments.replay_report.read_text(encoding="utf-8"))
                   if arguments.replay_report else None)
    output = json.dumps(run(source_rows), ensure_ascii=False, indent=2)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(output, encoding="utf-8")
        print(str(arguments.output.resolve()))
    else:
        print(output)
