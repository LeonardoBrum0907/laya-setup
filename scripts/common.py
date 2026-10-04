"""Shared helpers for the scripts in this folder."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "data" / "schema" / "ultron_schema.json"


def load_schema(path: Path = SCHEMA_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_env(path: Path = ROOT / ".env") -> None:
    """Load KEY=VALUE lines from .env into os.environ without overriding what is already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value:
            os.environ.setdefault(key, value)
    cache = os.environ.get("HF_HUB_CACHE")
    if cache and not Path(cache).is_absolute():
        os.environ["HF_HUB_CACHE"] = str((ROOT / cache).resolve())


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{n}: invalid JSON ({e})")
    return rows


def as_obj(value):
    """Official dataset rows store state/questions/gold as JSON strings; accept both."""
    return json.loads(value) if isinstance(value, str) else value
