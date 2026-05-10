"""Roll up raw_logs/**/*.jsonl into a per-(hardware, framework, model, task)
table that adds NTD cost-per-task using the assumptions in
COST_ASSUMPTIONS below.

Outputs:
  results/raw_runs.csv
  results/per_task_metrics.csv
  results/cost_per_task.csv

Be transparent: the article must show every input number and let the
reader recompute. Don't bury anything.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import fmean, pstdev


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW = ROOT / "raw_logs"
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)


# ---- COST ASSUMPTIONS (Taiwan, May 2026) -------------------------------
# Each number is justifiable to a reader. We expose them all so people
# can recompute with their own assumptions.
COST_ASSUMPTIONS = {
    "macmini-m4-32gb": {
        "hw_price_ntd": 36900,           # MacBook Air M4 32GB used as Mac mini surrogate (same M4, same 120 GB/s bandwidth)
        "amortise_years": 5,
        "active_hours_per_year": 2000,   # workstation usage: 8h/d × 250d
        "power_watts": 30,               # M4 sustained ~30W during inference
        "electricity_ntd_per_kwh": 3.0,  # rough Taiwan retail (residential)
        "datacentre_overhead_factor": 0.0,  # at-desk, no extra cooling
    },
    "h200-nvl-server": {
        "hw_price_ntd": 1_500_000,       # 1× H200 NVL ~NT$950k + dual-EPYC server NT$550k (2026 list, no rack)
        "amortise_years": 5,
        "active_hours_per_year": 8760,   # server: 24/7
        "power_watts": 1500,             # H200 ~700W typical + CPU+RAM = ~1.5 kW under load
        "electricity_ntd_per_kwh": 3.0,
        "datacentre_overhead_factor": 0.4,  # PUE 1.4 for typical Taiwan colocation
    },
}


def hourly_ntd(profile: dict) -> dict:
    """Return per-hour cost decomposition for a hardware profile."""
    yearly_hw = profile["hw_price_ntd"] / profile["amortise_years"]
    hw_per_hour = yearly_hw / profile["active_hours_per_year"]
    power_per_hour = profile["power_watts"] / 1000.0 * profile["electricity_ntd_per_kwh"]
    overhead_per_hour = power_per_hour * profile["datacentre_overhead_factor"]
    total = hw_per_hour + power_per_hour + overhead_per_hour
    return {
        "hw_ntd_per_hour": hw_per_hour,
        "power_ntd_per_hour": power_per_hour,
        "overhead_ntd_per_hour": overhead_per_hour,
        "total_ntd_per_hour": total,
    }


def percentile(values, q):
    s = sorted(values)
    if not s:
        return None
    k = (len(s) - 1) * q
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def main() -> int:
    raw_rows = []
    for p in sorted(RAW.rglob("*.jsonl")):
        with p.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                raw_rows.append({
                    "source": str(p.relative_to(ROOT)),
                    "hardware": rec.get("hardware", ""),
                    "framework": rec.get("framework", ""),
                    "model": rec.get("model", ""),
                    "quant": rec.get("quant", ""),
                    "task_id": rec.get("task_id", ""),
                    "run_id": rec.get("run_id", ""),
                    "label": rec.get("label", ""),
                    "ttft": rec.get("ttft", ""),
                    "end_to_end": rec.get("end_to_end", ""),
                    "decode_time": rec.get("decode_time", ""),
                    "output_tokens": rec.get("output_tokens", ""),
                    "output_chars": rec.get("output_chars", ""),
                    "decode_tok_s": rec.get("decode_tok_s", ""),
                    "output_text_hash": rec.get("output_text_hash", ""),
                    "prompt_chars": rec.get("prompt_chars", ""),
                    "max_tokens": rec.get("max_tokens", ""),
                    "timestamp": rec.get("timestamp", ""),
                })

    if not raw_rows:
        print("no jsonl rows under raw_logs/", file=sys.stderr)
        return 1

    raw_path = OUT / "raw_runs.csv"
    with raw_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(raw_rows[0].keys()))
        w.writeheader()
        w.writerows(raw_rows)
    print(f"wrote {raw_path} ({len(raw_rows)} rows)")

    # group by (hardware, framework, model, quant, task_id)
    groups = defaultdict(list)
    for r in raw_rows:
        key = (r["hardware"], r["framework"], r["model"], r["quant"], r["task_id"])
        groups[key].append(r)

    per_task_rows = []
    for key, rows in sorted(groups.items()):
        hw, fw, mdl, qnt, task = key
        e2es = [float(r["end_to_end"]) for r in rows if r["end_to_end"] != ""]
        ttfts = [float(r["ttft"]) for r in rows if r["ttft"] != ""]
        chars = [int(r["output_chars"]) for r in rows if r["output_chars"] != ""]
        hashes = {r["output_text_hash"] for r in rows if r["output_text_hash"]}
        per_task_rows.append({
            "hardware": hw,
            "framework": fw,
            "model": mdl,
            "quant": qnt,
            "task_id": task,
            "n": len(rows),
            "ttft_p50": percentile(ttfts, 0.5),
            "e2e_p50": percentile(e2es, 0.5),
            "e2e_p95": percentile(e2es, 0.95),
            "e2e_mean": fmean(e2es) if e2es else None,
            "e2e_stdev": pstdev(e2es) if len(e2es) > 1 else 0.0,
            "output_chars_mean": fmean(chars) if chars else None,
            "unique_hashes": len(hashes),
        })

    pt_path = OUT / "per_task_metrics.csv"
    with pt_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per_task_rows[0].keys()))
        w.writeheader()
        w.writerows(per_task_rows)
    print(f"wrote {pt_path} ({len(per_task_rows)} groups)")

    # cost rollup
    cost_rows = []
    for r in per_task_rows:
        hw = r["hardware"]
        profile_key = "macmini-m4-32gb" if hw.startswith("mac") else (
            "h200-nvl-server" if "h200" in hw else None
        )
        if profile_key is None:
            continue
        profile = COST_ASSUMPTIONS[profile_key]
        hourly = hourly_ntd(profile)
        e2e = r["e2e_p50"]
        if e2e is None:
            continue
        per_task_total = hourly["total_ntd_per_hour"] / 3600.0 * e2e
        per_task_hw_only = hourly["hw_ntd_per_hour"] / 3600.0 * e2e
        cost_rows.append({
            **r,
            "profile": profile_key,
            "hw_ntd_per_hour": round(hourly["hw_ntd_per_hour"], 4),
            "power_ntd_per_hour": round(hourly["power_ntd_per_hour"], 4),
            "overhead_ntd_per_hour": round(hourly["overhead_ntd_per_hour"], 4),
            "total_ntd_per_hour": round(hourly["total_ntd_per_hour"], 4),
            "ntd_per_task_total": round(per_task_total, 5),
            "ntd_per_task_hw_only": round(per_task_hw_only, 5),
        })

    if cost_rows:
        cp_path = OUT / "cost_per_task.csv"
        with cp_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(cost_rows[0].keys()))
            w.writeheader()
            w.writerows(cost_rows)
        print(f"wrote {cp_path} ({len(cost_rows)} rows)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
