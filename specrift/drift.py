from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from specrift.git_tools import WorkingChanges
from specrift.globmatch import match_any
from specrift.specs import SpecriftSpec


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    summary: str
    details: dict[str, Any] | None = None


def compute_spec_drift(
    *,
    task_id: str,
    task_title: str,
    description: str,
    spec: SpecriftSpec,
    git_root: str | None,
    changes: WorkingChanges | None,
) -> dict[str, Any]:
    findings: list[Finding] = []

    changed_files: list[str] = []
    if changes:
        changed_files = [
            p
            for p in changes.changed_files
            if not (p.startswith(".workgraph/") or p.startswith(".git/") or match_any(p, spec.ignore))
        ]

    telemetry: dict[str, Any] = {
        "files_changed": len(changed_files),
    }

    if spec.schema != 1:
        findings.append(
            Finding(
                kind="unsupported_schema",
                severity="warn",
                summary=f"Unsupported specrift schema: {spec.schema} (expected 1)",
            )
        )

    if not spec.spec:
        findings.append(
            Finding(
                kind="invalid_spec_config",
                severity="warn",
                summary="specrift spec[] is empty; nothing to keep in sync",
            )
        )

    spec_changed = [p for p in changed_files if match_any(p, spec.spec)]
    non_spec_changed = [p for p in changed_files if not match_any(p, spec.spec)]
    telemetry["spec_files_changed"] = len(spec_changed)
    telemetry["non_spec_files_changed"] = len(non_spec_changed)

    if spec.require_spec_update_when_code_changes and non_spec_changed and not spec_changed:
        findings.append(
            Finding(
                kind="spec_not_updated",
                severity="warn",
                summary="Non-spec files changed but no spec/doc files changed",
                details={
                    "spec_globs": spec.spec,
                    "changed_non_spec": non_spec_changed[:50],
                },
            )
        )

    score = "green"
    if any(f.severity == "warn" for f in findings):
        score = "yellow"
    if any(f.severity == "error" for f in findings):
        score = "red"

    recommendations: list[dict[str, Any]] = []
    for f in findings:
        if f.kind == "spec_not_updated":
            recommendations.append(
                {
                    "priority": "high",
                    "action": "Update spec/docs for this task (or adjust specrift spec globs)",
                    "rationale": "Spec drift is the fastest way to lose intent; keeping docs updated prevents hidden scope/perf regressions later.",
                }
            )
        elif f.kind == "invalid_spec_config":
            recommendations.append(
                {
                    "priority": "high",
                    "action": "Populate specrift spec[] with the docs/specs that should be updated for this task",
                    "rationale": "Specrift needs an explicit set of spec/doc paths to keep in sync.",
                }
            )
        elif f.kind == "unsupported_schema":
            recommendations.append(
                {
                    "priority": "high",
                    "action": "Set specrift schema = 1",
                    "rationale": "Only schema v1 is currently supported.",
                }
            )

    # De-dupe by action while preserving order.
    seen_actions: set[str] = set()
    recommendations = [r for r in recommendations if not (r["action"] in seen_actions or seen_actions.add(r["action"]))]  # type: ignore[arg-type]

    return {
        "task_id": task_id,
        "task_title": task_title,
        "git_root": git_root,
        "score": score,
        "spec": asdict(spec),
        "telemetry": telemetry,
        "findings": [asdict(f) for f in findings],
        "recommendations": recommendations,
    }

