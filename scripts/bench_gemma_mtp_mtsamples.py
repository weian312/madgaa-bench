"""Gemma 4 MTP / baseline benchmark over MTSamples prompts.

Wrapper around HF Transformers `model.generate(assistant_model=drafter)`
that loops over the v2.1 sampled MTSamples SOAP / DDx prompts. Same
JSONL schema as scripts/bench_mtsamples.py so aggregate_mtsamples.py
can fold the rows into the cross-validation table.

Usage:
  python bench_gemma_mtp_mtsamples.py \\
    --target google/gemma-4-E4B-it \\
    --assistant google/gemma-4-E4B-it-assistant \\
    --task soap_en --max-new-tokens 600 --warmup 1 --runs 5 \\
    --label "h200.transformers.gemma4-E4B.bf16.mtp" \\
    --hardware h200-nvl --framework "transformers-mtp" \\
    --out raw_logs_mtsamples/h200/gemma4_e4b_mtp_soap_en.jsonl

Pass --no-mtp to omit the drafter (HF Transformers baseline).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "datasets" / "mtsamples_sampled"


def hash_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--assistant", default=None)
    ap.add_argument("--no-mtp", action="store_true")
    ap.add_argument("--task", required=True, choices=["soap_en", "ddx_en"])
    ap.add_argument("--prompts-dir", default=None)
    ap.add_argument("--max-new-tokens", type=int, default=600)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--label", required=True)
    ap.add_argument("--hardware", required=True)
    ap.add_argument("--framework", required=True)
    ap.add_argument("--quant", default="bf16")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

    dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
    dtype = dtype_map[args.dtype]

    print(f"[{args.label}] loading tokenizer", file=sys.stderr)
    tok = AutoTokenizer.from_pretrained(args.target)
    print(f"[{args.label}] loading target: {args.target}", file=sys.stderr)
    t0 = time.perf_counter()
    target = AutoModelForCausalLM.from_pretrained(
        args.target, torch_dtype=dtype, device_map=args.device
    ).eval()
    target_load = time.perf_counter() - t0

    assistant = None
    if not args.no_mtp:
        if not args.assistant:
            print("ERROR: --assistant required unless --no-mtp", file=sys.stderr)
            return 2
        print(f"[{args.label}] loading assistant: {args.assistant}", file=sys.stderr)
        assistant = AutoModelForCausalLM.from_pretrained(
            args.assistant, torch_dtype=dtype, device_map=args.device
        ).eval()

    prompts_dir = Path(args.prompts_dir) if args.prompts_dir else SAMPLE_DIR / args.task
    prompt_files = sorted(prompts_dir.glob("*.txt"))
    if args.limit:
        prompt_files = prompt_files[: args.limit]
    if not prompt_files:
        raise SystemExit(f"no prompts in {prompts_dir}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[{args.label}] {len(prompt_files)} prompts × {args.runs} runs (+ warmup {args.warmup})", file=sys.stderr)

    def one_run(input_ids, attention_mask):
        streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=True)
        gen_kwargs = dict(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
            streamer=streamer,
        )
        if assistant is not None:
            gen_kwargs["assistant_model"] = assistant
        first_token_at = None
        last_token_at = None
        pieces = []
        token_count = 0
        request_start = time.perf_counter()
        thread = threading.Thread(target=lambda: target.generate(**gen_kwargs))
        thread.start()
        for piece in streamer:
            now = time.perf_counter()
            if not piece:
                continue
            if first_token_at is None:
                first_token_at = now
            pieces.append(piece)
            token_count += 1
            last_token_at = now
        thread.join()
        end = time.perf_counter()
        if first_token_at is None:
            first_token_at = end
        if last_token_at is None:
            last_token_at = end
        text = "".join(pieces)
        decode_time = max(last_token_at - first_token_at, 0.0)
        return {
            "ttft": first_token_at - request_start,
            "end_to_end": end - request_start,
            "decode_time": decode_time,
            "output_tokens": token_count,
            "output_chars": len(text),
            "decode_chars_per_s": len(text) / decode_time if decode_time > 0 else None,
            "decode_tok_s": token_count / decode_time if decode_time > 0 and token_count > 0 else None,
            "output_text": text,
            "output_text_hash": hash_text(text),
            "usage": None,
            "finish_reason": None,
        }

    n_done = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for pi, pfile in enumerate(prompt_files):
            prompt_text = pfile.read_text(encoding="utf-8")
            chat = [{"role": "user", "content": prompt_text}]
            rendered = tok.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
            tok_in = tok(rendered, return_tensors="pt").to(target.device)
            prompt_id = pfile.stem
            prompt_hash = hash_text(prompt_text)[:16]
            for _ in range(args.warmup):
                try:
                    one_run(tok_in.input_ids, tok_in.attention_mask)
                except Exception as e:
                    print(f"  warmup err {prompt_id}: {e}", file=sys.stderr)
            for run_idx in range(args.runs):
                try:
                    res = one_run(tok_in.input_ids, tok_in.attention_mask)
                except Exception as e:
                    print(f"  run err {prompt_id} run{run_idx}: {e}", file=sys.stderr)
                    continue
                row = {
                    **res,
                    "run_id": f"{prompt_id}_run{run_idx}",
                    "prompt_id": prompt_id,
                    "prompt_chars": len(prompt_text),
                    "prompt_hash": prompt_hash,
                    "label": args.label,
                    "hardware": args.hardware,
                    "framework": args.framework,
                    "model": args.target.split("/")[-1],
                    "quant": args.quant,
                    "task_id": args.task,
                    "max_tokens": args.max_new_tokens,
                    "mtp": not args.no_mtp,
                    "timestamp": time.time(),
                }
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                n_done += 1
            if (pi + 1) % 5 == 0:
                print(f"  [{pi+1}/{len(prompt_files)}] {n_done} runs", file=sys.stderr)

    print(f"done: {n_done} runs -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
