"""Medical-task benchmark over an OpenAI-compatible streaming endpoint.

For one (server, model, task) combo, runs N=warmup+runs requests at
temperature=0 and records per-run TTFT, e2e wall-clock, output chars,
output hash, and the prompt usage if the server returns one.

The output JSONL is the canonical raw artifact. cost-per-task analysis
is done downstream from these files (see compute_cost_per_task.py).

Usage:
  python3 bench_medical.py \\
    --base-url http://localhost:7777/v1 \\
    --model qwen3.6-35b \\
    --prompt prompts/task_A_soap_en.txt \\
    --task-id soap_en \\
    --hardware macmini-m4-32gb \\
    --framework rapidmlx \\
    --quant 4bit-mlx \\
    --max-tokens 600 \\
    --warmup 1 --runs 5 \\
    --out raw_logs/mac/soap_qwen36.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

import httpx


def hash_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def percentile(values, q):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def stream_one(
    client: httpx.Client,
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    extra_body: dict,
    api_key: str | None,
) -> dict:
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
    body.update(extra_body)
    url = base_url.rstrip("/") + "/chat/completions"

    request_start = time.perf_counter()
    first_token_at: float | None = None
    last_token_at: float | None = None
    output_tokens = 0
    pieces: list[str] = []
    usage = None
    finish_reason = None

    with client.stream("POST", url, json=body, headers=headers, timeout=900.0) as resp:
        resp.raise_for_status()
        for raw in resp.iter_lines():
            line = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            if event.get("usage"):
                usage = event["usage"]
            choices = event.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            piece = delta.get("content")
            if piece is None:
                continue
            now = time.perf_counter()
            if first_token_at is None and piece:
                first_token_at = now
            if piece:
                pieces.append(piece)
                output_tokens += 1
                last_token_at = now
            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]
    end = time.perf_counter()
    if first_token_at is None:
        first_token_at = end
    if last_token_at is None:
        last_token_at = end
    text = "".join(pieces)
    return {
        "ttft": first_token_at - request_start,
        "end_to_end": last_token_at - request_start,
        "decode_time": max(last_token_at - first_token_at, 0.0),
        "output_tokens": output_tokens,
        "output_chars": len(text),
        "decode_chars_per_s": (
            len(text) / (last_token_at - first_token_at)
            if last_token_at > first_token_at and len(text) > 0
            else None
        ),
        "decode_tok_s": (
            output_tokens / (last_token_at - first_token_at)
            if last_token_at > first_token_at and output_tokens > 0
            else None
        ),
        "output_text": text,
        "output_text_hash": hash_text(text),
        "usage": usage,
        "finish_reason": finish_reason,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--prompt", type=Path, required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--hardware", required=True)
    p.add_argument("--framework", required=True)
    p.add_argument("--quant", required=True)
    p.add_argument("--max-tokens", type=int, default=512)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--api-key", default=None)
    p.add_argument("--extra-body", default="{}")
    args = p.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    extra_body = json.loads(args.extra_body)
    prompt = args.prompt.read_text(encoding="utf-8")

    label = f"{args.hardware}.{args.framework}.{args.model.split('/')[-1]}.{args.quant}.{args.task_id}"
    client = httpx.Client()
    print(f"[{label}] warmup x{args.warmup}", file=sys.stderr)
    for _ in range(args.warmup):
        stream_one(
            client, args.base_url, args.model, prompt,
            args.max_tokens, args.temperature, extra_body, args.api_key,
        )
    runs: list[dict] = []
    with args.out.open("a", encoding="utf-8") as fh:
        for i in range(args.runs):
            r = stream_one(
                client, args.base_url, args.model, prompt,
                args.max_tokens, args.temperature, extra_body, args.api_key,
            )
            r["run_id"] = i
            r["label"] = label
            r["hardware"] = args.hardware
            r["framework"] = args.framework
            r["model"] = args.model
            r["quant"] = args.quant
            r["task_id"] = args.task_id
            r["prompt_file"] = str(args.prompt)
            r["prompt_chars"] = len(prompt)
            r["max_tokens"] = args.max_tokens
            r["timestamp"] = time.time()
            r_persisted = dict(r)
            r_persisted["output_text"] = r["output_text"][:600]
            fh.write(json.dumps(r_persisted, ensure_ascii=False) + "\n")
            fh.flush()
            runs.append(r)
            print(
                f"  run {i:02d}  TTFT={r['ttft']:.3f}s  e2e={r['end_to_end']:.3f}s  "
                f"out={r['output_chars']}c  ({r['output_tokens']}t)",
                file=sys.stderr,
            )

    e2es = [r["end_to_end"] for r in runs]
    ttfts = [r["ttft"] for r in runs]
    chars = [r["output_chars"] for r in runs]
    summary = {
        "label": label,
        "n": len(runs),
        "ttft_p50": percentile(ttfts, 0.5),
        "ttft_p95": percentile(ttfts, 0.95),
        "e2e_p50": percentile(e2es, 0.5),
        "e2e_p95": percentile(e2es, 0.95),
        "e2e_mean": statistics.fmean(e2es) if e2es else None,
        "e2e_stdev": statistics.pstdev(e2es) if len(e2es) > 1 else 0.0,
        "output_chars_mean": statistics.fmean(chars) if chars else None,
        "first_output_hash": runs[0]["output_text_hash"] if runs else None,
        "all_outputs_identical": len({r["output_text_hash"] for r in runs}) == 1,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
