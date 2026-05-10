"""Sample MTSamples prompts for SOAP + DDx benchmark cross-validation.

Reads the public MTSamples corpus (~5000 transcribed clinical reports,
Apache-2.0 via huggingface.co/datasets/harishnair04/mtsamples) and emits
deterministic random samples for each task type.

For SOAP summarisation:
  Filter to specialties with full SOAP-structured transcriptions
  (SOAP / Chart / Progress Notes, Discharge Summary, Consult).
  Each prompt: "Summarize the following clinical encounter into a SOAP
  format with 4 sections..." + transcription text.

For DDx reasoning:
  Filter to specialties resembling consult/ER/diagnostic-uncertainty
  cases (Consult, General Medicine, Emergency-like). Each prompt:
  "Given the following case, list the top 5 differential diagnoses..."
  + a chief-complaint-style excerpt from the transcription.

Output:
  datasets/mtsamples_sampled/soap_en/{i:03d}.txt  (one prompt per file)
  datasets/mtsamples_sampled/ddx_en/{i:03d}.txt
  datasets/mtsamples_sampled/index.jsonl  (id -> source_row, specialty, hash)

Usage:
  python sample_mtsamples.py --n-soap 30 --n-ddx 30 --seed 42
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "datasets" / "mtsamples.csv"
OUT_DIR = ROOT / "datasets" / "mtsamples_sampled"

SOAP_PROMPT_TEMPLATE = """You are a medical scribe. Summarize the following clinical encounter note into a SOAP format with exactly 4 sections (Subjective, Objective, Assessment, Plan). Each section must start with the letter on its own line followed by a colon (S:, O:, A:, P:). Use only information from the source.

CLINICAL NOTE:
{transcription}

SOAP SUMMARY:"""

DDX_PROMPT_TEMPLATE = """You are an attending physician on a consult service. Given the following case, list the top 5 most likely differential diagnoses ranked by probability. For each, give one line of reasoning grounded in the case findings. Output exactly 5 numbered items, no preamble.

CASE:
{case}

TOP 5 DIFFERENTIAL DIAGNOSES:"""

SOAP_SPECIALTIES = {
    "SOAP / Chart / Progress Notes",
    "Discharge Summary",
    "Consult - History and Phy.",
    "General Medicine",
    "Office Notes",
}

DDX_SPECIALTIES = {
    "Consult - History and Phy.",
    "General Medicine",
    "Emergency Room Reports",
    "Cardiovascular / Pulmonary",
    "Neurology",
    "Gastroenterology",
}


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def has_soap_structure(t: str) -> bool:
    """Heuristic: text contains both SUBJECTIVE/OBJECTIVE-style markers."""
    t_upper = (t or "").upper()
    return ("SUBJECTIVE" in t_upper or "HISTORY OF PRESENT ILLNESS" in t_upper) and (
        "OBJECTIVE" in t_upper or "PHYSICAL EXAM" in t_upper
    )


def chief_complaint_excerpt(t: str, max_chars: int = 1200) -> str:
    """Extract a chief-complaint + findings style excerpt from a long transcription."""
    if not t:
        return ""
    body = clean(t)
    if len(body) <= max_chars:
        return body
    return body[:max_chars].rsplit(".", 1)[0] + "."


def write_sample(out_dir: Path, idx: int, prompt_text: str, meta: dict, index_fp):
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{idx:03d}.txt"
    p.write_text(prompt_text, encoding="utf-8")
    h = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16]
    rec = {
        "task": meta["task"],
        "id": f"{meta['task']}_{idx:03d}",
        "source_row": meta["source_row"],
        "specialty": meta["specialty"],
        "sample_name": meta["sample_name"],
        "prompt_chars": len(prompt_text),
        "prompt_hash": h,
        "path": str(p.relative_to(ROOT)),
    }
    index_fp.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-soap", type=int, default=30)
    ap.add_argument("--n-ddx", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--max-soap-chars",
        type=int,
        default=2000,
        help="cap on transcription length included in SOAP prompt",
    )
    args = ap.parse_args()

    if not CSV.exists():
        raise SystemExit(f"missing {CSV} — run download first")

    df = pd.read_csv(CSV)
    df = df.fillna("")
    df["medical_specialty"] = df["medical_specialty"].str.strip()
    df["transcription"] = df["transcription"].astype(str)
    df["sample_name"] = df["sample_name"].str.strip()

    rng = random.Random(args.seed)

    # SOAP candidates
    soap_pool = df[df["medical_specialty"].isin(SOAP_SPECIALTIES)].copy()
    soap_pool = soap_pool[soap_pool["transcription"].apply(has_soap_structure)]
    soap_pool = soap_pool[soap_pool["transcription"].str.len().between(800, 4000)]
    print(f"SOAP candidate pool: {len(soap_pool)}")
    soap_idx = sorted(soap_pool.index.tolist())
    rng.shuffle(soap_idx)
    soap_picks = soap_idx[: args.n_soap]

    # DDx candidates
    ddx_pool = df[df["medical_specialty"].isin(DDX_SPECIALTIES)].copy()
    ddx_pool = ddx_pool[ddx_pool["description"].str.len().between(40, 400)]
    print(f"DDx candidate pool: {len(ddx_pool)}")
    ddx_idx = sorted(ddx_pool.index.tolist())
    rng.shuffle(ddx_idx)
    ddx_picks = ddx_idx[: args.n_ddx]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index_path = OUT_DIR / "index.jsonl"
    with index_path.open("w", encoding="utf-8") as idx_fp:
        for i, row_id in enumerate(soap_picks):
            row = df.loc[row_id]
            transcription = row["transcription"]
            if len(transcription) > args.max_soap_chars:
                transcription = transcription[: args.max_soap_chars].rsplit(".", 1)[0] + "."
            prompt = SOAP_PROMPT_TEMPLATE.format(transcription=clean(transcription))
            write_sample(
                OUT_DIR / "soap_en",
                i,
                prompt,
                {
                    "task": "soap_en",
                    "source_row": int(row_id),
                    "specialty": row["medical_specialty"],
                    "sample_name": row["sample_name"],
                },
                idx_fp,
            )

        for i, row_id in enumerate(ddx_picks):
            row = df.loc[row_id]
            description = row["description"]
            transcription = row["transcription"]
            case = clean(description) + "\n\n" + chief_complaint_excerpt(transcription, 800)
            prompt = DDX_PROMPT_TEMPLATE.format(case=case.strip())
            write_sample(
                OUT_DIR / "ddx_en",
                i,
                prompt,
                {
                    "task": "ddx_en",
                    "source_row": int(row_id),
                    "specialty": row["medical_specialty"],
                    "sample_name": row["sample_name"],
                },
                idx_fp,
            )

    print(f"wrote {args.n_soap} SOAP + {args.n_ddx} DDx prompts to {OUT_DIR}")
    print(f"index: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
