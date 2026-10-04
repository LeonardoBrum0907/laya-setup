"""Phase 5: expand the hand-written seed with an LLM.

For every seed example, asks Claude for N variants that keep the same labels: paraphrases,
colloquial Portuguese, sarcasm that stays sarcastic, and speech-transcription noise (no
punctuation, hesitations, swapped words). Variants whose labels drift, that duplicate each
other, or that collide with the frozen test set are dropped.

    python scripts/expand_dataset.py --dry-run                 # print the prompt for the first seed row
    python scripts/expand_dataset.py                           # all of data/seed -> data/train/expanded.jsonl
    python scripts/expand_dataset.py data/seed/provocacao.jsonl -n 12 --backend api

Backends:
  claude-code  (default) runs `claude -p` with your Claude Code login, no API key needed.
  api          calls the Claude API with the anthropic SDK (pip install anthropic; uses
               ANTHROPIC_API_KEY or an `ant auth login` profile).

The seed and the frozen test set are written by hand; this script never reads data/test_frozen
as input and never writes there.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, load_schema  # noqa: E402
from validate_dataset import TEST_DIR, check_label, collect, norm  # noqa: E402

MODEL = "claude-opus-5-5"
DEFAULT_OUT = ROOT / "data" / "train" / "expanded.jsonl"

SYSTEM = """Você gera variações de falas em português brasileiro para treinar um classificador de \
atos de fala de um assistente de voz chamado Ultron. As falas chegam já transcritas da voz.

Regras:
- Cada variação mantém exatamente os mesmos rótulos da fala original (mesmo ato, mesma \
intensidade, mesmo direcionamento, mesmo sarcasmo). Se uma variação mudaria um rótulo, não a escreva.
- Varie o vocabulário, a ordem, o registro (formal, gíria, regional) e o comprimento.
- Parte das variações deve imitar ruído de transcrição de fala: sem pontuação, tudo minúsculo, \
hesitações ("é...", "tipo", "hã"), repetições e uma ou outra palavra trocada por outra de som \
parecido. Marque essas com "noisy": true.
- Sarcasmo continua sarcástico; elogio sincero continua sincero.
- Não use nomes de pessoas reais nem dados pessoais.
- Só português brasileiro.

Rubrica de rotulagem (referência):
{rubric}"""

USER = """Fala original:
{transcript}

Rótulos (mantenha todos iguais em cada variação):
{labels}

Escreva {n} variações diferentes entre si e da original. Pelo menos {n_noisy} com ruído de transcrição.
Responda só com JSON no formato:
{{"variants": [{{"transcript": "...", "noisy": false, "labels": {{...os mesmos rótulos...}}}}]}}"""


def output_schema(questions: dict) -> dict:
    props = {}
    for qid, q in questions.items():
        if q["type"] == "choice":
            props[qid] = {"type": "string", "enum": list(q["criteria"])}
        elif q["type"] == "score":
            props[qid] = {"type": "integer", "enum": list(range(len(q["criteria"])))}
        else:
            props[qid] = {"type": "boolean"}
    return {
        "type": "object",
        "properties": {
            "variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "transcript": {"type": "string"},
                        "noisy": {"type": "boolean"},
                        "labels": {"type": "object", "properties": props,
                                   "required": list(props), "additionalProperties": False},
                    },
                    "required": ["transcript", "noisy", "labels"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["variants"],
        "additionalProperties": False,
    }


def extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in the answer")
    return json.loads(text[start:end + 1])


def ask_claude_code(system: str, prompt: str, schema: dict) -> dict:
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("`claude` (Claude Code) not found on PATH. Install it or use --backend api.")
    full = f"{system}\n\n---\n\n{prompt}"
    out = subprocess.run([exe, "-p", "--output-format", "json"], input=full, capture_output=True,
                         text=True, encoding="utf-8", timeout=600)
    if out.returncode != 0:
        raise RuntimeError(f"claude -p failed: {out.stderr.strip()[:300]}")
    envelope = json.loads(out.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"claude -p error: {str(envelope.get('result'))[:300]}")
    return extract_json(envelope.get("result", ""))


def ask_api(system: str, prompt: str, schema: dict) -> dict:
    try:
        import anthropic
    except ImportError:
        raise SystemExit("pip install anthropic (inside the venv) to use --backend api.")
    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("the model declined this example")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("answer cut off at max_tokens")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


BACKENDS = {"claude-code": ask_claude_code, "api": ask_api}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, default=[ROOT / "data" / "seed"])
    parser.add_argument("-n", "--variants", type=int, default=8, help="variants per seed example")
    parser.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--backend", choices=list(BACKENDS), default="claude-code")
    parser.add_argument("--limit", type=int, default=None, help="only the first N seed examples")
    parser.add_argument("--dry-run", action="store_true", help="print the first prompt and exit")
    args = parser.parse_args()

    test_root = TEST_DIR.resolve()
    for p in args.paths:
        rp = p.resolve()
        if rp == test_root or test_root in rp.parents:
            sys.exit("Refusing to expand data/test_frozen: it must never feed training data.")

    schema = load_schema()
    questions = schema["questions"]
    rubric = (ROOT / "data" / "rubric.md").read_text(encoding="utf-8")
    system = SYSTEM.format(rubric=rubric)
    seed = [r for rows in collect([p.resolve() for p in args.paths]).values() for r in rows]
    seed = seed[: args.limit] if args.limit else seed
    if not seed:
        sys.exit("No seed examples found. Write them in data/seed/ first (see data/seed/README.md).")

    blocked = {norm(r["state"]["transcript"]) for rows in collect([test_root]).values() for r in rows}
    seen = {norm(r["state"]["transcript"]) for r in seed}
    if args.out.exists():
        for line in args.out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen.add(norm(json.loads(line)["state"]["transcript"]))
    done_ids = set()
    if args.out.exists():
        done_ids = {json.loads(l)["id"].rsplit("-x", 1)[0] for l in args.out.read_text(encoding="utf-8").splitlines() if l.strip()}

    out_schema = output_schema(questions)
    ask = BACKENDS[args.backend]
    if args.dry_run:
        row = next((r for r in seed if r["id"] not in done_ids), seed[0])
        print(system, "\n\n---\n\n", USER.format(
            transcript=row["state"]["transcript"], labels=json.dumps(row["labels"], ensure_ascii=False),
            n=args.variants, n_noisy=max(1, args.variants // 3)), sep="")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    kept = dropped = failed = 0
    with open(args.out, "a", encoding="utf-8") as f:
        for i, row in enumerate(seed, 1):
            if row["id"] in done_ids:
                continue  # resumable: already expanded in a previous run
            labels = row["labels"]
            prompt = USER.format(transcript=row["state"]["transcript"],
                                 labels=json.dumps(labels, ensure_ascii=False),
                                 n=args.variants, n_noisy=max(1, args.variants // 3))
            try:
                answer = ask(system, prompt, out_schema)
            except Exception as e:  # one bad example should not stop the run
                failed += 1
                print(f"[{i}/{len(seed)}] {row['id']}: failed ({e})", file=sys.stderr)
                continue
            k = 0
            for v in answer.get("variants", []):
                text = str(v.get("transcript", "")).strip()
                key = norm(text)
                drift = {q: v.get("labels", {}).get(q) for q in labels if v.get("labels", {}).get(q) != labels[q]}
                bad = [check_label(questions[q], val) for q, val in v.get("labels", {}).items() if q in questions]
                if not key or key in seen or key in blocked or drift or any(bad):
                    dropped += 1
                    continue
                seen.add(key)
                k += 1
                f.write(json.dumps({
                    "id": f"{row['id']}-x{k}",
                    "lang": "pt",
                    "noisy": bool(v.get("noisy", False)),
                    "source": f"expanded:{args.backend}",
                    "state": {**row["state"], "transcript": text},
                    "labels": labels,
                }, ensure_ascii=False) + "\n")
                kept += 1
            f.flush()
            print(f"[{i}/{len(seed)}] {row['id']}: +{k}")
    print(f"kept {kept}, dropped {dropped} (duplicate, label drift or test collision), failed {failed}")
    print("next: python scripts/validate_dataset.py")


if __name__ == "__main__":
    main()
