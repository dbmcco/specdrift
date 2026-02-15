from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from specrift.contracts import format_default_contract_block
from specrift.drift import compute_spec_drift
from specrift.git_tools import get_git_root, get_working_changes
from specrift.specs import SpecriftSpec, extract_specrift_spec, parse_specrift_spec
from specrift.workgraph import Workgraph, find_workgraph_dir


class ExitCode:
    ok = 0
    findings = 3
    usage = 2


def _run(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def _emit_text(report: dict) -> None:
    task_id = report.get("task_id")
    title = report.get("task_title")
    score = report.get("score")
    findings = report.get("findings") or []

    print(f"{task_id}: {title}")
    print(f"score: {score}")
    if not findings:
        print("findings: none")
        return

    print("findings:")
    for f in findings:
        print(f"- [{f.get('severity')}] {f.get('kind')}: {f.get('summary')}")


def _write_state(*, wg_dir: Path, report: dict) -> None:
    try:
        out_dir = wg_dir / ".specrift"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "last.json").write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    except Exception:
        # Best-effort; never fail a check on state write.
        pass


def _maybe_write_log(wg: Workgraph, task_id: str, report: dict) -> None:
    findings = report.get("findings") or []
    score = report.get("score", "unknown")
    recs = report.get("recommendations") or []

    if not findings:
        msg = "Specrift: OK (no findings)"
    else:
        kinds = ", ".join(sorted({str(f.get("kind")) for f in findings}))
        msg = f"Specrift: {score} ({kinds})"
        if recs:
            next_action = str(recs[0].get("action") or "").strip()
            if next_action:
                msg += f" | next: {next_action}"

    wg.wg_log(task_id, msg)


def _maybe_create_followups(wg: Workgraph, report: dict) -> None:
    task_id = str(report["task_id"])
    task_title = str(report.get("task_title") or task_id)
    spec_raw = report.get("spec") or {}
    spec = SpecriftSpec.from_raw(spec_raw)

    findings = report.get("findings") or []
    if not findings:
        return

    for f in findings:
        kind = str(f.get("kind") or "")
        if kind != "spec_not_updated":
            continue

        follow_id = f"drift-spec-{task_id}"
        title = f"spec: {task_title}"
        # Keep the follow-up narrowly scoped to spec globs; Speedrift will flag scope drift if it expands.
        desc = (
            "Update the task specs/docs to match current code changes.\n\n"
            "Context:\n"
            f"- Origin task: {task_id}\n"
            f"- Finding: {f.get('summary')}\n\n"
            + format_default_contract_block(mode="core", objective=title, touch=spec.spec)
            + "\n"
            + (report.get("_specrift_block") or "").strip()
            + "\n"
        )
        wg.ensure_task(
            task_id=follow_id,
            title=title,
            description=desc,
            blocked_by=[task_id],
            tags=["drift", "spec"],
        )


def _load_task(*, wg: Workgraph, task_id: str) -> dict:
    task = wg.show_task(task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")
    return task


def cmd_wg_check(args: argparse.Namespace) -> int:
    if not args.task:
        print("error: --task is required", file=sys.stderr)
        return ExitCode.usage

    wg_dir = find_workgraph_dir(Path(args.dir) if args.dir else None)
    project_dir = wg_dir.parent
    wg = Workgraph(wg_dir=wg_dir, project_dir=project_dir)

    task_id = str(args.task)
    task = _load_task(wg=wg, task_id=task_id)
    title = str(task.get("title") or task_id)
    description = str(task.get("description") or "")

    raw_block = extract_specrift_spec(description)
    if raw_block is None:
        report = {
            "task_id": task_id,
            "task_title": title,
            "git_root": None,
            "score": "green",
            "spec": None,
            "telemetry": {"note": "no specrift block"},
            "findings": [],
            "recommendations": [],
        }
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=False))
        else:
            _emit_text(report)
        return ExitCode.ok

    try:
        spec_raw = parse_specrift_spec(raw_block)
        spec = SpecriftSpec.from_raw(spec_raw)
    except Exception as e:
        report = {
            "task_id": task_id,
            "task_title": title,
            "git_root": None,
            "score": "yellow",
            "spec": None,
            "telemetry": {"parse_error": str(e)},
            "findings": [
                {
                    "kind": "invalid_specrift_spec",
                    "severity": "warn",
                    "summary": "specrift block present but could not be parsed",
                }
            ],
            "recommendations": [
                {
                    "priority": "high",
                    "action": "Fix the specrift TOML block so it parses",
                    "rationale": "Specrift can only advise on spec drift when it can read the spec configuration.",
                }
            ],
        }
        report["_specrift_block"] = f"```specrift\n{raw_block}\n```"
        _write_state(wg_dir=wg_dir, report=report)
        if args.write_log:
            _maybe_write_log(wg, task_id, report)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=False))
        else:
            _emit_text(report)
        return ExitCode.findings

    git_root = get_git_root(project_dir)
    changes = get_working_changes(git_root) if git_root else None

    report = compute_spec_drift(
        task_id=task_id,
        task_title=title,
        description=description,
        spec=spec,
        git_root=git_root,
        changes=changes,
    )
    report["_specrift_block"] = f"```specrift\n{raw_block}\n```"

    _write_state(wg_dir=wg_dir, report=report)

    if args.write_log:
        _maybe_write_log(wg, task_id, report)
    if args.create_followups:
        _maybe_create_followups(wg, report)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=False))
    else:
        _emit_text(report)

    return ExitCode.findings if report.get("findings") else ExitCode.ok


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="specrift")
    p.add_argument("--dir", help="Project directory (or .workgraph dir). Defaults to cwd search.")
    p.add_argument("--json", action="store_true", help="JSON output (where supported)")

    sub = p.add_subparsers(dest="cmd", required=True)

    wg = sub.add_parser("wg", help="Workgraph-integrated commands")
    wg_sub = wg.add_subparsers(dest="wg_cmd", required=True)

    check = wg_sub.add_parser("check", help="Check for spec drift (requires a specrift block in the task)")
    check.add_argument("--task", help="Task id to check")
    check.add_argument("--write-log", action="store_true", help="Write summary into wg log")
    check.add_argument("--create-followups", action="store_true", help="Create follow-up tasks for findings")
    check.set_defaults(func=cmd_wg_check)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

