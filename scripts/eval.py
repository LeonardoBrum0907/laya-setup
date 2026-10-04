"""Phase 6: evaluate perception against the frozen test set.

Compares sources side by side: Laya checkpoints served by scripts/serve.py (one per --model),
an optional fine-tuned checkpoint (same server, started with that model), and the rules fallback
from the TypeScript client. Splits every metric by language and by noisy / clean transcripts.

    python scripts/eval.py                                   # multilingual + rules on data/test_frozen
    python scripts/eval.py --model english --model multilingual --no-rules
    python scripts/eval.py --test data/seed                  # plumbing check on the seed

Writes reports/eval-<timestamp>.md and .json, plus reports/review_queue.jsonl with low-confidence
answers and Laya/rules disagreements for manual labelling.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, load_env, load_schema  # noqa: E402
from validate_dataset import TEST_DIR, collect  # noqa: E402

ECE_BINS = 10


def laya_predict(base_url: str, api_key: str | None, model: str, state: dict, questions: dict) -> dict:
    body = json.dumps({"state": state, "questions": questions, "model": model}).encode()
    req = urllib.request.Request(f"{base_url}/v1/systemone", data=body, method="POST",
                                 headers={"content-type": "application/json"})
    if api_key:
        req.add_header("authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())["answers"]


def rules_predict(rows: list[dict]) -> list[dict]:
    """Runs the TS rules fallback over every transcript in one node process."""
    script = ROOT / "client" / "scripts" / "rules-predict.ts"
    payload = "\n".join(json.dumps(r["state"], ensure_ascii=False) for r in rows)
    out = subprocess.run(["node", str(script)], input=payload, capture_output=True, text=True,
                         encoding="utf-8", check=True)
    return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]


def predicted(question: dict, answer: dict):
    """Returns (predicted label, confidence) in the label space of the authoring format."""
    t = question["type"]
    if t == "choice":
        return answer["choice"], answer.get("answer_confidence", answer.get("confidence"))
    if t == "score":
        probs = answer.get("probabilities") or {}
        if probs:
            level = max(probs, key=lambda k: probs[k])
            return int(level), probs[level]
        return int(round(answer["score"])), answer.get("answer_confidence")
    p = answer["noul"]
    return p >= 0.5, max(p, 1 - p)


def ece(pairs: list[tuple[float, bool]]) -> float | None:
    pairs = [(c, ok) for c, ok in pairs if c is not None]
    if not pairs:
        return None
    bins: dict[int, list] = defaultdict(list)
    for c, ok in pairs:
        bins[min(int(c * ECE_BINS), ECE_BINS - 1)].append((c, ok))
    total = len(pairs)
    return sum(len(b) / total * abs(sum(c for c, _ in b) / len(b) - sum(ok for _, ok in b) / len(b))
               for b in bins.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", type=Path, default=TEST_DIR)
    parser.add_argument("--model", action="append", help="laya checkpoint served by scripts/serve.py")
    parser.add_argument("--no-rules", action="store_true")
    parser.add_argument("--url", default=None, help="default http://LAYA_HOST:LAYA_PORT")
    parser.add_argument("--review-below", type=float, default=0.6, help="confidence under which answers go to review")
    args = parser.parse_args()

    load_env()
    url = args.url or f"http://{os.environ.get('LAYA_HOST', '127.0.0.1')}:{os.environ.get('LAYA_PORT', '8000')}"
    api_key = os.environ.get("LAYA_API_KEY") or None
    schema = load_schema()
    questions = schema["questions"]
    rows = [r for rs in collect([args.test.resolve()]).values() for r in rs]
    if not rows:
        sys.exit(f"No examples under {args.test}. Write the frozen test set first (see data/test_frozen/README.md).")

    sources: dict[str, list[dict | None]] = {}
    for model in args.model or ["multilingual"]:
        preds = []
        for r in rows:
            try:
                preds.append(laya_predict(url, api_key, model, r["state"], {q: questions[q] for q in r["labels"]}))
            except (urllib.error.URLError, OSError) as e:
                sys.exit(f"laya-serve not reachable at {url} ({e}). Start it with: python scripts/serve.py")
        sources[f"laya:{model}"] = preds
    if not args.no_rules:
        sources["rules"] = rules_predict(rows)

    report: dict = {"test": str(args.test), "n": len(rows), "sources": {}}
    review = []
    for name, preds in sources.items():
        stats: dict = defaultdict(lambda: {"n": 0, "correct": 0, "conf": []})
        confusion: dict = defaultdict(lambda: defaultdict(int))
        for row, answers in zip(rows, preds):
            for qid, gold in row["labels"].items():
                ans = (answers or {}).get(qid)
                if ans is None:
                    continue
                label, conf = predicted(questions[qid], ans)
                ok = label == gold
                slices = ["all", f"lang={row['lang']}", f"noisy={bool(row.get('noisy', False))}"]
                for s in slices:
                    st = stats[(qid, s)]
                    st["n"] += 1
                    st["correct"] += ok
                    st["conf"].append((conf, ok))
                if questions[qid]["type"] == "choice":
                    confusion[qid][f"{gold} -> {label}"] += 1
                if name.startswith("laya") and conf is not None and conf < args.review_below:
                    review.append({"id": row["id"], "source": name, "question": qid, "reason": "low_confidence",
                                   "transcript": row["state"]["transcript"], "predicted": label, "confidence": conf})
        report["sources"][name] = {
            "metrics": {f"{q} [{s}]": {"n": v["n"], "accuracy": round(v["correct"] / v["n"], 4),
                                       "ece": None if ece(v["conf"]) is None else round(ece(v["conf"]), 4)}
                        for (q, s), v in sorted(stats.items())},
            "confusion": {q: dict(sorted(c.items())) for q, c in confusion.items()},
        }

    if "rules" in sources:
        for name, preds in sources.items():
            if not name.startswith("laya"):
                continue
            for row, a, b in zip(rows, preds, sources["rules"]):
                la, lb = (a or {}).get("act_type"), (b or {}).get("act_type")
                if la and lb and la["choice"] != lb["choice"]:
                    review.append({"id": row["id"], "source": f"{name} vs rules", "question": "act_type",
                                   "reason": "disagreement", "transcript": row["state"]["transcript"],
                                   "predicted": {name: la["choice"], "rules": lb["choice"]}})

    out_dir = ROOT / "reports"
    out_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out_dir / f"eval-{stamp}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out_dir / "review_queue.jsonl", "w", encoding="utf-8") as f:
        for item in review:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    lines = [f"# Eval {stamp}", "", f"Test set: `{args.test}` ({len(rows)} examples). URL: {url}", ""]
    for name, src in report["sources"].items():
        lines += [f"## {name}", "", "| question [slice] | n | accuracy | ECE |", "|---|---|---|---|"]
        for key, m in src["metrics"].items():
            ece_txt = "" if m["ece"] is None else f"{m['ece']:.3f}"
            lines.append(f"| {key} | {m['n']} | {m['accuracy']:.3f} | {ece_txt} |")
        for q, c in src["confusion"].items():
            lines += ["", f"Confusion `{q}` (gold -> predicted):", ""]
            lines += [f"- {k}: {v}" for k, v in c.items()]
        lines.append("")
    lines.append(f"Review queue: {len(review)} items in reports/review_queue.jsonl")
    md = out_dir / f"eval-{stamp}.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {md.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
