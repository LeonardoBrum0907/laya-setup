"""Phase 5: validate labelled examples against the schema.

Checks every *.jsonl under the given folders: required fields, labels valid for each question,
exact and near duplicates (normalized transcript), and leakage between training data and
data/test_frozen/.

    python scripts/validate_dataset.py                  # data/seed + data/train vs data/test_frozen
    python scripts/validate_dataset.py data/seed

Authoring format, one JSON object per line (questions come from the schema, never repeated here):

    {"id": "seed-0001", "lang": "pt", "noisy": false,
     "state": {"transcript": "...", "device": "desktop", "channel": "voice"},
     "labels": {"act_type": "provocation", "intensity": 2, "directed_at_ultron": true, "is_sarcastic": false}}
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, load_schema, read_jsonl  # noqa: E402

TRAIN_DIRS = [ROOT / "data" / "seed", ROOT / "data" / "train"]
TEST_DIR = ROOT / "data" / "test_frozen"
LANGS = {"pt"}  # schema ultron-v1: Portuguese only for now; add "en" here when that changes


def norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if ROOT in path.parents else str(path)


def check_label(question: dict, value) -> str | None:
    t = question["type"]
    if t == "choice":
        if value not in question["criteria"]:
            return f"not one of {sorted(question['criteria'])}"
    elif t == "score":
        n = len(question["criteria"])
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < n:
            return f"must be an integer level 0..{n - 1}"
    elif t == "noul":
        if not isinstance(value, bool):
            return "must be true or false"
    return None


def validate_rows(path: Path, rows: list[dict], schema: dict, errors: list[str]) -> None:
    questions = schema["questions"]
    for n, row in enumerate(rows, 1):
        where = f"{rel(path)}:{n}"
        for key in ("id", "lang", "state", "labels"):
            if key not in row:
                errors.append(f"{where}: missing '{key}'")
        if row.get("lang") not in LANGS:
            errors.append(f"{where}: lang must be one of {sorted(LANGS)}")
        if "noisy" in row and not isinstance(row["noisy"], bool):
            errors.append(f"{where}: noisy must be true or false")
        state = row.get("state", {})
        if not isinstance(state, dict) or not str(state.get("transcript", "")).strip():
            errors.append(f"{where}: state.transcript is required")
        if isinstance(state, dict) and ("mood" in state or "emotions" in state):
            errors.append(f"{where}: the state must not carry Ultron's mood")
        labels = row.get("labels", {})
        if not labels:
            errors.append(f"{where}: no labels")
        for qid, value in labels.items():
            if qid not in questions:
                errors.append(f"{where}: unknown question '{qid}'")
                continue
            problem = check_label(questions[qid], value)
            if problem:
                errors.append(f"{where}: {qid}={value!r} {problem}")


def collect(dirs: list[Path]) -> dict[Path, list[dict]]:
    files = {}
    for d in dirs:
        if d.is_file():
            files[d] = read_jsonl(d)
        elif d.is_dir():
            for p in sorted(d.rglob("*.jsonl")):
                files[p] = read_jsonl(p)
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, help="files or folders of training data")
    parser.add_argument("--test", type=Path, default=TEST_DIR)
    args = parser.parse_args()

    schema = load_schema()
    train = collect([p.resolve() for p in args.paths] or TRAIN_DIRS)
    test = collect([args.test.resolve()])
    errors: list[str] = []
    warnings: list[str] = []

    for path, rows in {**train, **test}.items():
        validate_rows(path, rows, schema, errors)

    seen_ids: dict[str, Path] = {}
    for path, rows in {**train, **test}.items():
        for row in rows:
            rid = row.get("id")
            if rid in seen_ids:
                errors.append(f"duplicate id '{rid}' in {path.name} and {seen_ids[rid].name}")
            seen_ids[rid] = path

    def texts(files):
        out: dict[str, str] = {}
        for path, rows in files.items():
            for row in rows:
                t = norm(str(row.get("state", {}).get("transcript", "")))
                if t:
                    if t in out and files is train:
                        warnings.append(f"duplicate transcript in training data: '{t[:60]}' ({row.get('id')})")
                    out.setdefault(t, row.get("id"))
        return out

    train_texts = texts(train)
    test_texts = texts(test)
    for t, rid in test_texts.items():
        if t in train_texts:
            errors.append(f"LEAK: test '{rid}' also appears in training data as '{train_texts[t]}'")

    counts: dict[str, int] = {}
    for rows in train.values():
        for row in rows:
            act = row.get("labels", {}).get("act_type")
            if act:
                counts[act] = counts.get(act, 0) + 1

    n_train = sum(len(r) for r in train.values())
    n_test = sum(len(r) for r in test.values())
    print(f"training examples: {n_train} in {len(train)} files; frozen test: {n_test} in {len(test)} files")
    if counts:
        print("act_type counts (training): " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    if errors:
        sys.exit(1)
    print("ok")


if __name__ == "__main__":
    main()
