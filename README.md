# specdrift

`specdrift` is a Speedrift-suite sidecar that detects **spec/documentation drift** without hard-blocking development.

It is designed to be run under Workgraph tasks via the `driftdriver`/`drifts` unified check.

## Ecosystem Map

This project is part of the Speedrift suite for Workgraph-first drift control.

- Spine: [Workgraph](https://graphwork.github.io/)
- Orchestrator: [driftdriver](https://github.com/dbmcco/driftdriver)
- Baseline lane: [speedrift](https://github.com/dbmcco/speedrift)
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

Exit codes:
- `0`: clean
- `3`: findings exist (advisory)
