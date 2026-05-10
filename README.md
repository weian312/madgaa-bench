# madgaa-bench v2 — Mac mini vs H200 NVL · medical AI inference CP value

> Companion repo for [一台 Mac mini 能不能取代一張 H200？](https://madgaa.com/blog/p/medical-ai-9-models-mac-vs-h200-cp-value-blog-2026-05?lang=zh) (Madgaa Engineering · 2026-05)

This repository contains every raw run, every prompt, every script, and every figure that produced the article's NT$ numbers. **The article's claim is reproducibility — this repo is the proof.**

## What's measured

- **9 local LLMs** (Qwen 3.6 35B-A3B · Qwen3-Next 80B-A3B · Gemma 4 26B-A4B · Gemma 4 31B · MedGemma 27B-text-it · MedGemma 4B-it · Phi-4 14B · Mistral Small 3.2 24B · GLM 4.7-Flash) all at **4-bit quant** (MLX on Mac, GGUF Q4_K_M on H200)
- **2 hardwares** — Mac mini-class (MacBook Air M4 32GB 120 GB/s, proxy for Mac mini M4 base; recommended config in article is M4 Pro 48GB 273 GB/s) vs H200 NVL server (NT$1.5M class)
- **4 clinical tasks** — SOAP summary (en) · DDx reasoning (en) · Drug interaction QA (zh) · ICD-10 coding (zh)
- **52 cells × 5 runs each** — full deterministic check via SHA256 of output text

## How to reproduce

```bash
# 1. Clone this repo
git clone https://github.com/madgaa/madgaa-bench.git
cd madgaa-bench

# 2. Look at our numbers (no compute required)
cat results/cost_per_task.csv           # NT$/task per (hw, model, task) cell
cat results/raw_runs.csv                # every individual run
ls raw_logs/{h200,mac}/                 # JSONL with full output text + hash

# 3. Re-run on your own hardware (requires the model + framework)
python scripts/bench_medical.py \
    --task soap_en \
    --hardware your-host \
    --model qwen36-35b-a3b \
    --runs 5

# 4. Compute YOUR per-task NT$ with YOUR clinic's numbers
edit scripts/compute_cost_per_task.py     # change COST_ASSUMPTIONS dict
python scripts/compute_cost_per_task.py   # writes results/cost_per_task.csv

# 5. Re-plot
python scripts/plot_v2.py                 # writes figures/01_*.png .. 06_*.png
```

## Layout

```
v2/
├── article/                 markdown source for the blog post
├── prompts/                 4 clinical task prompts (de-id)
├── env/                     OS / driver / CUDA / MLX versions
├── raw_logs/
│   ├── h200/                JSONL per (model, task), one line per run
│   └── mac/                 same
├── results/
│   ├── raw_runs.csv         flat table of every run
│   ├── per_task_metrics.csv p50/p95/mean per cell
│   └── cost_per_task.csv    NT$/task — article's source of truth
├── figures/                 the 6 figures in the blog post (1600px)
├── scripts/
│   ├── bench_medical.py            benchmark runner
│   ├── compute_cost_per_task.py    NT$ + COST_ASSUMPTIONS
│   ├── plot_v2.py                  figure generator
│   └── run_{h200,mac}_*sweep.sh    invocation wrappers
└── CLAUDE.md                engineering / publishing rules
```

## Cost assumptions (from `compute_cost_per_task.py`)

| | Mac mini M4 Pro 48GB | H200 NVL server |
|---|---:|---:|
| Hardware (incl. tax) | NT$54,900 | NT$1,500,000 |
| Amortisation period | 5 years | 5 years |
| Hours / year | 8,760 (24/7) | 8,760 (24/7) |
| Inference power | 30 W | 1,500 W |
| Electricity rate | NT$3.0 / kWh | NT$3.0 / kWh |
| PUE | 1.0 (desk-side) | 1.4 (datacenter) |
| **Total NT$/hr** | **NT$1.34** | **NT$40.55** |

Per-task NT$ = (e2e seconds / 3600) × NT$/hr.

## Headline result

For the same SOAP prompt on Qwen 3.6 35B-A3B Q4:

| | e2e | NT$ / task | Notes |
|---|---:|---:|---|
| Mac mini M4 Pro 48GB | 11.48 s | **NT$0.0043** | 5 runs byte-identical |
| H200 NVL | 2.08 s | NT$0.0234 | 5 runs byte-identical |
| **Mac vs H200** | **5.5× slower** | **5.5× cheaper** | cross-HW hashes differ (chars: 1357 vs 1384) |

Across 9 models × 4 tasks, **Mac mini wins cheapest on all 4 tasks**. H200 wins fastest on all 4 (via MedGemma 4B-it).

Break-even ≈ 5.5 concurrent users — until then, Mac mini is strictly cheaper per task in single-user clinical workflows.

## Limitations (honest)

- Tested Mac is M4 base 120 GB/s; **recommended Mac mini M4 Pro is 273 GB/s** — expected ~2× faster than reported numbers
- Quality is checked via determinism + character count only — **no clinician double-blind grading**. Don't deploy without your own quality eval
- 4-bit quant medical-task hallucination not independently studied
- Concurrency advantage of H200 (Fig 4) is **linearly extrapolated** from single-user numbers, not measured at batch=N
- Reasoning models (DeepSeek R1 distill, GPT-OSS 20B) excluded — they emit empty visible content despite `--no-thinking` (5/5 SHA256 = e3b0c44…, the empty-string hash)
- Prompts are **internal de-identified representative cases**, not public dataset. Next iteration will use [MTSamples](https://www.mtsamples.com) for public-data cross-validation

## License

Code: MIT. Raw logs and figures: CC-BY-4.0. Prompts are de-identified synthetic representative cases — no PHI.

## Citation

```
@misc{madgaa_bench_2026_05,
  title  = {Mac mini vs H200 NVL: Per-task cost on 9 local LLMs across 4 clinical tasks},
  author = {Madgaa Engineering},
  year   = {2026},
  month  = {May},
  url    = {https://github.com/madgaa/madgaa-bench}
}
```
