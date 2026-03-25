# specdrift

`specdrift` is a Speedrift-suite sidecar that detects **spec/documentation drift** without hard-blocking development.

It is designed to be run under Workgraph tasks via the `driftdriver`/`drifts` unified check.

## North Star

**North Star**: specdrift reliably identifies when spec/doc files have drifted from code changes, enabling Workgraph agents to receive actionable, low-noise advisory findings that keep documentation honest without blocking delivery.

## Ecosystem Map

This project is part of the Speedrift suite for Workgraph-first drift control.

- Spine: [Workgraph](https://graphwork.github.io/)
- Orchestrator: [driftdriver](https://github.com/dbmcco/driftdriver)
- Baseline lane: [coredrift](https://github.com/dbmcco/coredrift)
- Optional lanes: [specdrift](https://github.com/dbmcco/specdrift), [datadrift](https://github.com/dbmcco/datadrift), [depsdrift](https://github.com/dbmcco/depsdrift), [uxdrift](https://github.com/dbmcco/uxdrift), [therapydrift](https://github.com/dbmcco/therapydrift), [yagnidrift](https://github.com/dbmcco/yagnidrift), [redrift](https://github.com/dbmcco/redrift)

## Task Spec Format

Add a per-task fenced TOML block:

````md
```specdrift
schema = 1
spec = [
  "README.md",
  "docs/**",
]
require_spec_update_when_code_changes = true
```
````

Semantics:
- `spec`: repo-root-relative globs. `*` matches within a segment; `**` matches multiple segments (same as Speedrift touch globs).
- When `require_spec_update_when_code_changes = true`, if any non-spec file changes in the working tree and **no** `spec` file changes, `specdrift` emits an advisory finding and (optionally) spawns a follow-up task.

## Workgraph Integration

From a Workgraph repo (where `driftdriver install` has written wrappers):

```bash
./.workgraph/drifts check --task <id> --write-log --create-followups
```

Standalone (from a repo root):

```bash
/path/to/specdrift/bin/specdrift --dir . wg check --task <id> --write-log --create-followups
```

## Speedrift Agent Control

When `specdrift` is installed into a repo through Speedrift:

- Workgraph remains the task source of truth.
- `speedriftd` owns repo-local runtime supervision.
- Default repo posture is `observe`; agent sessions should refresh/report state before asking the repo to continue background work.
- Use the repo lifecycle hooks and explicit mode changes rather than treating `wg service start` as the generic startup path.
- The shared agent docs written by `driftdriver install --all-clis` explain the exact `session-start`, `task-claimed`, `task-completing`, and `speedriftd status --set-mode ...` commands.

Exit codes:
- `0`: clean
- `3`: findings exist (advisory)
