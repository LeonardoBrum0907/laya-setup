"""Convert authoring-format examples to the official Laya training format.

The official fine-tuning code (notebooks/laya_finetune_typed_decisions_*.py in NandhaKishorM/laya)
reads rows whose `state`, `questions` and `gold` are JSON *strings*, with
gold = {question_id: {"probabilities": {...}}}:
  choice -> keyed by option name, noul -> keyed by "false"/"true", score -> keyed by "0".."n-1".

    python scripts/export_dataset.py data/seed data/train -o build/train.jsonl
    python scripts/export_dataset.py data/seed --smoothing 0.05 -o build/train.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, load_schema  # noqa: E402
from validate_dataset import TEST_DIR, collect  # noqa: E402


def gold_for(question: dict, value, smoothing: float) -> dict:
    t = question["type"]
    if t == "choice":
        keys = list(question["criteria"])
    elif t == "score":
        keys = [str(i) for i in range(len(question["criteria"]))]
        value = str(value)
    else:
        keys = ["false", "true"]
        value = "true" if value else "false"
    rest = smoothing / (len(keys) - 1) if len(keys) > 1 else 0.0
    return {"probabilities": {k: round(1.0 - smoothing if k == value else rest, 6) for k in keys}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("-o", "--out", type=Path, required=True)
    parser.add_argument("--smoothing", type=float, default=0.0, help="label smoothing mass spread over other options")
    args = parser.parse_args()

    test_root = TEST_DIR.resolve()
    for p in args.paths:
        rp = p.resolve()
        if rp == test_root or test_root in rp.parents:
            sys.exit("Refusing to export data/test_frozen: it must never be used for training.")

    questions = load_schema()["questions"]
    files = collect([p.resolve() for p in args.paths])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for rows in files.values():
            for row in rows:
                qs = {qid: questions[qid] for qid in row["labels"]}
                gold = {qid: gold_for(questions[qid], v, args.smoothing) for qid, v in row["labels"].items()}
                f.write(json.dumps({
                    "id": row["id"],
                    "state": json.dumps(row["state"], ensure_ascii=False),
                    "questions": json.dumps(qs, ensure_ascii=False),
                    "gold": json.dumps(gold, ensure_ascii=False),
                }, ensure_ascii=False) + "\n")
                n += 1
    print(f"wrote {n} rows to {args.out.relative_to(ROOT) if ROOT in args.out.resolve().parents else args.out}")


if __name__ == "__main__":
    main()
