"""Aggregate MTSamples bench raw_logs into per-(hardware, model, task) stats.

For each (hardware, model, task) cell:
  - aggregate across all sampled prompts and runs
  - compute median, p95, mean, std, 95% CI (BCa-bootstrap on the median)
  - per-prompt determinism check: same prompt should yield same hash within 5 runs

Apply COST_ASSUMPTIONS (same as v2 / compute_cost_per_task.py) to convert
e2e -> NT$/task.

Output:
  results/mtsamples_per_task_metrics.csv  (one row per cell)
  results/mtsamples_cost_per_task.csv     (with NT$/task and 95% CI)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_logs_mtsamples"
OUT = ROOT / "results"

COST_ASSUMPTIONS = {
    "macmini-m4-pro-48gb": {
        "price_ntd": 54900,
        "amort_years": 5,
        "hr_per_year": 8760,
        "infer_watt": 30,
        "elec_ntd_per_kwh": 3.0,
        "pue": 1.0,
    },
    "h200-nvl": {
        "price_ntd": 1_500_000,
        "amort_years": 5,
        "hr_per_year": 8760,
        "infer_watt": 1500,
        "elec_ntd_per_kwh": 3.0,
        "pue": 1.4,
    },
}


def cost_per_hour(hw_key: str) -> float:
    a = COST_ASSUMPTIONS[hw_key]
    amort = a["price_ntd"] / (a["amort_years"] * a["hr_per_year"])
    elec = a["infer_watt"] * a["elec_ntd_per_kwh"] * a["pue"] / 1000
    return amort + elec


def percentile(values, q):
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * q
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def bootstrap_ci_median(values, n_resamples=1000, seed=42):
    """BCa-light: percentile bootstrap CI for the median."""
    if len(values) < 2:
        return float("nan"), float("nan")
    import random
    rng = random.Random(seed)
    medians = []
    n = len(values)
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))
    return percentile(medians, 0.025), percentile(medians, 0.975)


def normalise_hardware(label: str) -> str:
    if label.startswith("h200"):
        return "h200-nvl"
    if label.startswith("mac"):
        return "macmini-m4-pro-48gb"
    return label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs-dir", default=str(RAW))
    ap.add_argument("--out-dir", default=str(OUT))
    args = ap.parse_args()

    logs = sorted(Path(args.logs_dir).rglob("*.jsonl"))
    print(f"reading {len(logs)} log files")

    cells = defaultdict(list)
    determinism = defaultdict(lambda: defaultdict(set))
    for fp in logs:
        for line in fp.open(encoding="utf-8"):
            r = json.loads(line)
            hw = normalise_hardware(r.get("hardware", "unknown"))
            model = r["model"]
            task = r["task_id"]
            key = (hw, model, task)
            cells[key].append(r)
            determinism[key][r["prompt_id"]].add(r["output_text_hash"][:32])

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_csv = out_dir / "mtsamples_per_task_metrics.csv"
    cost_csv = out_dir / "mtsamples_cost_per_task.csv"

    with metrics_csv.open("w", newline="", encoding="utf-8") as mf, \
         cost_csv.open("w", newline="", encoding="utf-8") as cf:
        mw = csv.writer(mf)
        cw = csv.writer(cf)
        mw.writerow([
            "hardware", "model", "task_id", "n_prompts", "n_runs",
            "e2e_p50", "e2e_p95", "e2e_mean", "e2e_std",
            "e2e_ci_lo", "e2e_ci_hi",
            "ttft_p50", "output_chars_mean", "deterministic_per_prompt",
        ])
        cw.writerow([
            "hardware", "model", "task_id",
            "n_prompts", "n_runs",
            "e2e_p50", "ntd_per_task", "ntd_per_task_ci_lo", "ntd_per_task_ci_hi",
        ])

        for (hw, model, task), runs in sorted(cells.items()):
            e2e = [r["end_to_end"] for r in runs if r.get("end_to_end")]
            if not e2e:
                continue
            ttft = [r["ttft"] for r in runs if r.get("ttft") is not None]
            chars = [r["output_chars"] for r in runs]
            n_prompts = len({r["prompt_id"] for r in runs})
            n_runs = len(runs)
            e2e_p50 = percentile(e2e, 0.5)
            e2e_p95 = percentile(e2e, 0.95)
            e2e_mean = statistics.fmean(e2e)
            e2e_std = statistics.pstdev(e2e) if len(e2e) > 1 else 0.0
            ci_lo, ci_hi = bootstrap_ci_median(e2e)
            det = all(len(h) == 1 for h in determinism[(hw, model, task)].values())

            mw.writerow([
                hw, model, task, n_prompts, n_runs,
                f"{e2e_p50:.4f}", f"{e2e_p95:.4f}", f"{e2e_mean:.4f}", f"{e2e_std:.4f}",
                f"{ci_lo:.4f}", f"{ci_hi:.4f}",
                f"{percentile(ttft,0.5):.4f}" if ttft else "",
                f"{statistics.fmean(chars):.0f}",
                str(det),
            ])

            hph = cost_per_hour(hw)
            ntd = e2e_p50 * hph / 3600
            ntd_lo = ci_lo * hph / 3600
            ntd_hi = ci_hi * hph / 3600
            cw.writerow([
                hw, model, task, n_prompts, n_runs,
                f"{e2e_p50:.4f}", f"{ntd:.5f}", f"{ntd_lo:.5f}", f"{ntd_hi:.5f}",
            ])

    print(f"wrote {metrics_csv}")
    print(f"wrote {cost_csv}")
    print()
    print("--- summary ---")
    for (hw, model, task), runs in sorted(cells.items()):
        e2e = [r["end_to_end"] for r in runs if r.get("end_to_end")]
        if not e2e:
            continue
        n_prompts = len({r["prompt_id"] for r in runs})
        e2e_p50 = percentile(e2e, 0.5)
        ci_lo, ci_hi = bootstrap_ci_median(e2e)
        ntd = e2e_p50 * cost_per_hour(hw) / 3600
        det = all(len(h) == 1 for h in determinism[(hw, model, task)].values())
        print(
            f"{hw:30s} {model:30s} {task:12s} "
            f"n={n_prompts:3d}p×{len(runs)//max(n_prompts,1)}r "
            f"p50={e2e_p50:6.2f}s  CI=[{ci_lo:.2f},{ci_hi:.2f}]  "
            f"NT${ntd:.5f}  det={'Y' if det else 'N'}"
        )


if __name__ == "__main__":
    sys.exit(main())
