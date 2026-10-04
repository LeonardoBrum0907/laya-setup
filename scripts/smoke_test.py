"""Phase 1 smoke test: load a checkpoint, ask one choice, one score and one noul question.

Prints each answer with its probabilities, plus cold (first call, includes load) and warm latency.

    python scripts/smoke_test.py                       # multilingual checkpoint, default sentence
    python scripts/smoke_test.py --model english --text "you are way too slow, hurry up"
    python scripts/smoke_test.py --offline             # same, with HF_HUB_OFFLINE=1 (after a first download)
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from common import load_env, load_schema  # noqa: E402

DEFAULT_TEXT = "Ultron, você é lento demais, anda logo com isso."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--model", default="multilingual", help="english | multilingual | typed-decisions")
    parser.add_argument("--device", default=None, help="cpu | cuda | xpu | mps (default: LAYA_DEVICE or auto)")
    parser.add_argument("--offline", action="store_true", help="set HF_HUB_OFFLINE=1 before importing laya")
    parser.add_argument("--warm-runs", type=int, default=5)
    args = parser.parse_args()

    load_env()
    if args.offline:
        os.environ["HF_HUB_OFFLINE"] = "1"

    from laya import Router  # imported late so the env vars above apply

    schema = load_schema()
    q = schema["questions"]
    questions = {name: q[name] for name in ("act_type", "intensity", "directed_at_ultron")}
    state = {"transcript": args.text, "device": "desktop", "channel": "voice"}

    device = args.device or os.environ.get("LAYA_DEVICE") or None
    router = Router(device=device) if device else Router()

    t0 = time.perf_counter()
    result = router.predict(state, questions, model=args.model)
    cold_ms = (time.perf_counter() - t0) * 1000

    warm = []
    for _ in range(args.warm_runs):
        t0 = time.perf_counter()
        router.predict(state, questions, model=args.model)
        warm.append((time.perf_counter() - t0) * 1000)
    warm.sort()

    print(f"text   : {args.text}")
    print(f"routing: {result.get('routing')}")
    for name, ans in result["answers"].items():
        value = ans.get(ans["type"])
        print(f"\n[{ans['type']}] {name} = {value}  (answer_confidence={ans.get('answer_confidence')})")
        if "probabilities" in ans:
            for label, p in ans["probabilities"].items():
                legend = ans.get("legend", {}).get(label, "")
                print(f"    {label:<16} {p:.4f}  {legend}")
    print(f"\ncold   : {cold_ms:.0f} ms (includes checkpoint load)")
    print(f"warm   : median {warm[len(warm) // 2]:.1f} ms, min {warm[0]:.1f} ms over {len(warm)} runs")
    print(f"offline: {os.environ.get('HF_HUB_OFFLINE') == '1'}")


if __name__ == "__main__":
    main()
