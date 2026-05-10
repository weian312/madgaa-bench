"""MTSamples benchmark — iterate sampled clinical prompts on a model.

Per-prompt: 1 warmup + N runs. Outputs one JSONL line per run with
prompt_id, ttft, e2e, output_chars, output_hash. Same downstream
schema as bench_medical.py so compute_cost_per_task.py can aggregate.

Usage:
  python bench_mtsamples.py \\
    --base-url http://localhost:7777/v1 \\
    --model qwen3.6-35b-a3b-q4_k_m \\
    --hardware h200-nvl \\
    --framework llamacpp \\
    --quant 4bit-gguf \\
    --task soap_en \\
    --max-tokens 600 \\
    --runs 5 \\
    --out raw_logs_mtsamples/h200/qwen36_35b_soap_en.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "datasets" / "mtsamples_sampled"


def hash_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def stream_one(
    client, base_url, model, prompt, max_tokens, temperature, extra_body, api_key
):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    body.update(extra_body or {})
    url = base_url.rstrip("/") + "/chat/completions"

    request_start = time.perf_counter()
    first_token_at = None
    last_token_at = None
    output_tokens = 0
    pieces = []
    usage = None
    finish_reason = None

    with client.stream("POST", url, json=body, headers=headers, timeout=180.0) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8", "replace")
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            choice = (obj.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            content = delta.get("content") or ""
            if content:
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                last_token_at = time.perf_counter()
                pieces.append(content)
                output_tokens += 1
            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]
            if obj.get("usage"):
                usage = obj["usage"]

    end_time = time.perf_counter()
    output_text = "".join(pieces)
    ttft = (first_token_at - request_start) if first_token_at else None
    e2e = end_time - request_start
    decode_time = (
        (last_token_at - first_token_at) if (first_token_at and last_token_at) else None
    )
    return {
        "ttft": ttft,
        "end_to_end": e2e,
        "decode_time": decode_time,
        "output_tokens": output_tokens,
        "output_chars": len(output_text),
        "decode_chars_per_s": (len(output_text) / decode_time) if decode_time else None,
        "decode_tok_s": (output_tokens / decode_time) if decode_time else None,
        "output_text": output_text,
        "output_text_hash": hashlib.sha256(output_text.encode("utf-8")).hexdigest(),
        "usage": usage,
        "finish_reason": finish_reason,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--hardware", required=True)
    ap.add_argument("--framework", required=True)
    ap.add_argument("--quant", default="4bit")
    ap.add_argument("--task", required=True, choices=["soap_en", "ddx_en"])
    ap.add_argument("--prompts-dir", default=None,
                    help="override; default = datasets/mtsamples_sampled/<task>")
    ap.add_argument("--max-tokens", type=int, default=600)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None,
                    help="cap the number of prompts (for smoke test)")
    ap.add_argument("--no-thinking", action="store_true",
                    help="add chat_template_kwargs={enable_thinking:false}")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    prompts_dir = Path(args.prompts_dir) if args.prompts_dir else SAMPLE_DIR / args.task
    if not prompts_dir.exists():
        raise SystemExit(f"missing prompts dir: {prompts_dir}")
    prompt_files = sorted(prompts_dir.glob("*.txt"))
    if args.limit:
        prompt_files = prompt_files[: args.limit]
    if not prompt_files:
        raise SystemExit("no prompt files found")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    extra_body = {}
    if args.no_thinking:
        extra_body["chat_template_kwargs"] = {"enable_thinking": False}

    print(f"task={args.task} prompts={len(prompt_files)} model={args.model}")
    n_done = 0
    with httpx.Client() as client, out_path.open("w", encoding="utf-8") as out_fp:
        for pi, pfile in enumerate(prompt_files):
            prompt = pfile.read_text(encoding="utf-8")
            prompt_id = pfile.stem
            prompt_hash = hash_text(prompt)
            for w in range(args.warmup):
                try:
                    stream_one(
                        client, args.base_url, args.model, prompt,
                        args.max_tokens, args.temperature, extra_body, args.api_key,
                    )
                except Exception as e:
                    print(f"  warmup err {prompt_id}: {e}", file=sys.stderr)
            for run_idx in range(args.runs):
                try:
                    res = stream_one(
                        client, args.base_url, args.model, prompt,
                        args.max_tokens, args.temperature, extra_body, args.api_key,
                    )
                except Exception as e:
                    print(f"  run err {prompt_id} run{run_idx}: {e}", file=sys.stderr)
                    continue
                row = {
                    **res,
                    "run_id": f"{prompt_id}_run{run_idx}",
                    "prompt_id": prompt_id,
                    "prompt_chars": len(prompt),
                    "prompt_hash": prompt_hash,
                    "label": f"{args.hardware}/{args.model}/{args.task}",
                    "hardware": args.hardware,
                    "framework": args.framework,
                    "model": args.model,
                    "quant": args.quant,
                    "task_id": args.task,
                    "max_tokens": args.max_tokens,
                    "timestamp": time.time(),
                }
                out_fp.write(json.dumps(row, ensure_ascii=False) + "\n")
                out_fp.flush()
                n_done += 1
            if (pi + 1) % 5 == 0:
                print(f"  [{pi+1}/{len(prompt_files)}] {n_done} runs done")

    print(f"done: {n_done} runs -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
