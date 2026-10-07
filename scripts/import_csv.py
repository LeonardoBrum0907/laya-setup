"""Import a reviewed spreadsheet (CSV) into the dataset as JSONL.

The drafts in data/drafts/ are CSV files you can open in Excel or Google Sheets: fix the labels,
delete rows you don't want, add your own, save as CSV (semicolon or comma), then import:

    python scripts/import_csv.py data/drafts/test_draft.csv --to test     # -> data/test_frozen/test.jsonl
    python scripts/import_csv.py data/drafts/seed_draft.csv --to seed     # -> data/seed/seed.jsonl

Columns: id; transcript; act_type; intensity (0-3); directed_at_ultron; is_sarcastic; noisy.
Yes/no columns accept sim/nao, s/n, true/false, 1/0, x/blank. Optional columns: device, channel.
Every row is checked against the schema before anything is written; nothing is written if a row
is wrong. The output file is replaced, so the CSV stays the source you edit.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, load_schema  # noqa: E402
from validate_dataset import check_label, rel  # noqa: E402

TARGETS = {"seed": ROOT / "data" / "seed" / "seed.jsonl", "test": ROOT / "data" / "test_frozen" / "test.jsonl"}
YES = {"sim", "s", "yes", "y", "true", "1", "x", "verdadeiro"}
NO = {"nao", "não", "n", "no", "false", "0", "", "falso"}


def to_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in YES:
        return True
    if v in NO:
        return False
    raise ValueError(f"'{value}' is not yes/no")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--to", choices=list(TARGETS), required=True)
    parser.add_argument("-o", "--out", type=Path, default=None, help="override the output file")
    args = parser.parse_args()

    questions = load_schema()["questions"]
    text = args.csv.read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=";,\t")
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    required = {"id", "transcript", "act_type", "intensity", "directed_at_ultron", "is_sarcastic", "noisy"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        sys.exit(f"missing columns: {sorted(missing)}")

    rows, errors, ids = [], [], set()
    for n, r in enumerate(reader, 2):
        if not (r.get("transcript") or "").strip():
            continue  # blank line in the sheet
        where = f"{args.csv.name}:{n}"
        try:
            labels = {
                "act_type": r["act_type"].strip(),
                "intensity": int(r["intensity"]),
                "directed_at_ultron": to_bool(r["directed_at_ultron"]),
                "is_sarcastic": to_bool(r["is_sarcastic"]),
            }
            noisy = to_bool(r["noisy"])
        except ValueError as e:
            errors.append(f"{where}: {e}")
            continue
        for qid, value in labels.items():
            problem = check_label(questions[qid], value)
            if problem:
                errors.append(f"{where}: {qid}={value!r} {problem}")
        rid = r["id"].strip() or f"{args.to}-{n:04d}"
        if rid in ids:
            errors.append(f"{where}: duplicate id {rid}")
        ids.add(rid)
        rows.append({
            "id": rid,
            "lang": "pt",
            "noisy": noisy,
            "state": {"transcript": r["transcript"].strip(),
                      "device": (r.get("device") or "desktop").strip() or "desktop",
                      "channel": (r.get("channel") or "voice").strip() or "voice"},
            "labels": labels,
        })

    if errors:
        print("\n".join(f"error: {e}" for e in errors))
        sys.exit(f"{len(errors)} problem(s); nothing written.")
    out = args.out or TARGETS[args.to]
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} examples to {rel(out)}")
    print("next: python scripts/validate_dataset.py")


if __name__ == "__main__":
    main()
