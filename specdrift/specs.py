from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from typing import Any


FENCE_INFO = "specdrift"

_FENCE_RE = re.compile(
    r"```(?P<info>specdrift)\s*\n(?P<body>.*?)\n```",
    re.DOTALL,
)


def extract_specdrift_spec(description: str) -> str | None:
    m = _FENCE_RE.search(description or "")
    if not m:
        return None
    return m.group("body").strip()


def parse_specdrift_spec(text: str) -> dict[str, Any]:
    data = tomllib.loads(text)
    if not isinstance(data, dict):
        raise ValueError("specdrift block must parse to a TOML table/object.")
    return data


@dataclass(frozen=True)
class SpecdriftSpec:
    schema: int
    spec: list[str]
    require_spec_update_when_code_changes: bool
    ignore: list[str]

    @staticmethod
    def from_raw(raw: dict[str, Any]) -> "SpecdriftSpec":
        schema = int(raw.get("schema", 1))
        spec = [str(x) for x in (raw.get("spec") or [])]
        require_update = bool(raw.get("require_spec_update_when_code_changes", True))
        ignore = [str(x) for x in (raw.get("ignore") or [])]
        # Always ignore workgraph internals, even if not configured.
        ignore = [*ignore, ".workgraph/**", ".git/**"]
        return SpecdriftSpec(
            schema=schema,
            spec=spec,
            require_spec_update_when_code_changes=require_update,
            ignore=ignore,
        )
