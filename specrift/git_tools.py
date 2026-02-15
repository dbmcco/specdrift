from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


def get_git_root(project_dir: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(project_dir), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or None
    except Exception:
        return None


@dataclass(frozen=True)
class WorkingChanges:
    changed_files: list[str]


def _git_lines(args: list[str], *, cwd: str) -> list[str]:
    try:
        out = subprocess.check_output(["git", "-C", cwd, *args], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    return [l for l in out.splitlines() if l.strip()]


def get_working_changes(git_root: str) -> WorkingChanges:
    unstaged = set(_git_lines(["diff", "--name-only"], cwd=git_root))
    staged = set(_git_lines(["diff", "--name-only", "--cached"], cwd=git_root))
    untracked = set(_git_lines(["ls-files", "--others", "--exclude-standard"], cwd=git_root))

    changed = sorted(unstaged | staged | untracked)
    return WorkingChanges(changed_files=changed)

