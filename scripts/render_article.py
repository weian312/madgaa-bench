"""Fill placeholders in article.md template using results/cost_per_task.csv.

Identifies the strongest model per task (lowest NTD per task), then
generates the headline finding and per-task table rows.

Output: article/article_filled.md
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RES = ROOT / "results" / "cost_per_task.csv"
SRC = ROOT / "article" / "article.md"
DST = ROOT / "article" / "article_filled.md"


HW_ZH = {
    "macmini-m4-32gb": "Mac mini-class",
    "h200-nvl": "H200 NVL",
}


MODEL_DISPLAY = {
    "qwen3.6-35b-a3b": "Qwen 3.6 35B-A3B",
    "qwen3.6-35b": "Qwen 3.6 35B-A3B",
    "qwen3.6-35b-a3b-q4_k_m": "Qwen 3.6 35B-A3B",
    "gemma-4-26b-a4b-it-4bit": "Gemma 4 26B-A4B",
    "gemma-4-26b-a4b-it": "Gemma 4 26B-A4B",
    "gemma-4-26B-A4B-it": "Gemma 4 26B-A4B",
    "gemma-4-31b-it": "Gemma 4 31B",
    "gemma-4-31B-it": "Gemma 4 31B",
    "medgemma-27b-text-it": "MedGemma 27B-text-it",
    "medgemma-4b-it": "MedGemma 4B-it",
    "phi-4-4bit": "Phi-4 14B",
    "phi-4": "Phi-4 14B",
    "GLM-4.7-4bit": "GLM 4.7-Flash",
    "glm-4.7-flash": "GLM 4.7-Flash",
    "GPT-OSS-20B-4bit": "GPT-OSS 20B",
    "gpt-oss-20b": "GPT-OSS 20B",
    "Mistral-Small-3.2-24B-Instruct-2506-4bit": "Mistral Small 3.2 24B",
    "mistral-small-3.2-24b": "Mistral Small 3.2 24B",
    "DeepSeek-R1-Distill-Qwen-32B-4bit": "DeepSeek R1 Distill 32B",
    "deepseek-r1-32b": "DeepSeek R1 Distill 32B",
    "qwen3-next-80b-a3b": "Qwen3-Next 80B-A3B",
}


def normalise_model(m: str) -> str:
    if m in MODEL_DISPLAY:
        return MODEL_DISPLAY[m]
    # try basename-style fallback
    for k, v in MODEL_DISPLAY.items():
        if k.lower() in m.lower():
            return v
    return m


def f(v):
    try:
        return float(v) if v not in ("", None, "None") else None
    except (TypeError, ValueError):
        return None


def main() -> int:
    if not RES.exists():
        print(f"missing {RES}; run compute_cost_per_task.py first")
        return 1
    rows = list(csv.DictReader(RES.open()))
    by_task: dict[str, list[dict]] = {}
    for r in rows:
        by_task.setdefault(r["task_id"], []).append(r)

    article = SRC.read_text(encoding="utf-8")

    # Per-task tables
    task_label = {
        "soap_en": "SOAP",
        "ddx_en": "DDx",
        "drug_zh": "用藥諮詢",
        "icd_zh": "ICD-10",
    }
    table_placeholders = {
        "soap_en": "TBD: SOAP_TABLE_ROWS",
        "ddx_en": "TBD: DDX_TABLE_ROWS",
        "drug_zh": "TBD: DRUG_TABLE_ROWS",
        "icd_zh": "TBD: ICD_TABLE_ROWS",
    }
    for task_id, rs in by_task.items():
        if task_id not in table_placeholders:
            continue
        lines = []
        rs_sorted = sorted(rs, key=lambda r: f(r["ntd_per_task_total"]) or 1e9)
        for r in rs_sorted:
            hw = HW_ZH.get(r["hardware"], r["hardware"])
            mdl = normalise_model(r["model"])
            e2e = f(r["e2e_p50"])
            chars = f(r["output_chars_mean"])
            cost = f(r["ntd_per_task_total"])
            unique = r["unique_hashes"]
            note = "byte-identical" if unique == "1" else f"{unique} variants"
            lines.append(
                f"| {hw} | {mdl} | "
                f"{e2e:.2f} | "
                f"{int(chars) if chars else '—'} | "
                f"{cost:.5f} | {note} |"
            )
        article = article.replace(
            table_placeholders[task_id], "\n".join(lines), 1
        )

    # Headline finding: lowest NT$ per task on Mac for SOAP
    mac_soap = [r for r in by_task.get("soap_en", []) if r["hardware"].startswith("mac")]
    mac_soap_sorted = sorted(mac_soap, key=lambda r: f(r["ntd_per_task_total"]) or 1e9)
    h200_soap = [r for r in by_task.get("soap_en", []) if r["hardware"].startswith("h200")]
    h200_soap_sorted = sorted(h200_soap, key=lambda r: f(r["ntd_per_task_total"]) or 1e9)

    if mac_soap_sorted and h200_soap_sorted:
        mac_best = mac_soap_sorted[0]
        h200_best = h200_soap_sorted[0]
        mac_best_model = normalise_model(mac_best["model"])
        h200_best_model = normalise_model(h200_best["model"])
        mac_cost = f(mac_best["ntd_per_task_total"]) or 0
        h200_cost = f(h200_best["ntd_per_task_total"]) or 0
        mac_e2e = f(mac_best["e2e_p50"]) or 0
        h200_e2e = f(h200_best["e2e_p50"]) or 0
        # find a med-specific model winner if any
        med_h200 = [
            r for r in by_task.get("soap_en", [])
            if r["hardware"].startswith("h200")
            and "medgemma" in r["model"].lower()
        ]
        med_best = sorted(med_h200, key=lambda r: f(r["ntd_per_task_total"]) or 1e9)[0] if med_h200 else None

        headline = (
            f"我們在 SOAP 摘要任務上的最低成本贏家：**Mac mini-class + {mac_best_model}**"
            f"（每張 NT${mac_cost:.4f}、wall-clock {mac_e2e:.2f}s），"
            f"比 **H200 NVL + {h200_best_model}**（每張 NT${h200_cost:.4f}、{h200_e2e:.2f}s）"
            f"**便宜 {h200_cost / mac_cost:.2f}× 但慢 {mac_e2e / h200_e2e:.1f}×**。"
            "對 single-user 醫療診間這是一個明確選擇。"
        )
        article = article.replace(
            "TBD: HEADLINE_FINDING_TO_BE_FILLED", headline
        )
        article = article.replace("MAC_BEST_MODEL", mac_best_model)
        article = article.replace("H200_BEST_MODEL", h200_best_model)
        if med_best:
            med_model = normalise_model(med_best["model"])
            article = article.replace("MEDICAL_BEST_MODEL", med_model)

    # Per-task winner table
    winner_rows = {}
    for task_id, rs in by_task.items():
        if task_id not in task_label:
            continue
        rs_sorted = sorted(rs, key=lambda r: f(r["ntd_per_task_total"]) or 1e9)
        rs_speed = sorted(rs, key=lambda r: f(r["e2e_p50"]) or 1e9)
        cheapest = rs_sorted[0] if rs_sorted else None
        fastest = rs_speed[0] if rs_speed else None
        if cheapest and fastest:
            ch = HW_ZH.get(cheapest["hardware"], cheapest["hardware"])
            cm = normalise_model(cheapest["model"])
            cc = f(cheapest["ntd_per_task_total"]) or 0
            fh = HW_ZH.get(fastest["hardware"], fastest["hardware"])
            fm = normalise_model(fastest["model"])
            fe = f(fastest["e2e_p50"]) or 0
            winner_rows[task_id] = (
                f"| 單張 {task_label[task_id]} | {fh} / {fm} ({fe:.2f}s) | {ch} / {cm} (NT${cc:.4f}) |"
            )

    return write(article, winner_rows)


def write(article: str, winner_rows: dict) -> int:
    # blog-style TL;DR has bold headers + _TBD_; replace with bold winner lines
    blog_old = (
        "| 維度 | 最快冠軍 | 最便宜冠軍 |\n"
        "|---|---|---|\n"
        "| **單張 SOAP 摘要** | _TBD_ | _TBD_ |\n"
        "| **單張 DDx 推理** | _TBD_ | _TBD_ |\n"
        "| **中文用藥諮詢** | _TBD_ | _TBD_ |\n"
        "| **中文 ICD 編碼** | _TBD_ | _TBD_ |"
    )
    blog_new = (
        "| 維度 | 最快冠軍 | 最便宜冠軍 |\n"
        "|---|---|---|\n"
        + (winner_rows.get('soap_en', '| **單張 SOAP 摘要** | _TBD_ | _TBD_ |').replace('| 單張 SOAP 摘要 |', '| **單張 SOAP 摘要** |')) + "\n"
        + (winner_rows.get('ddx_en', '| **單張 DDx 推理** | _TBD_ | _TBD_ |').replace('| 單張 DDx 推理 |', '| **單張 DDx 推理** |')) + "\n"
        + (winner_rows.get('drug_zh', '| **中文用藥諮詢** | _TBD_ | _TBD_ |').replace('| 中文用藥諮詢 |', '| **中文用藥諮詢** |')) + "\n"
        + (winner_rows.get('icd_zh', '| **中文 ICD 編碼** | _TBD_ | _TBD_ |').replace('| 中文 ICD 編碼 |', '| **中文 ICD 編碼** |'))
    )
    article = article.replace(blog_old, blog_new)

    # also handle the v3 plain format if present
    plain_old = (
        "| 維度 | 最快冠軍 | 最便宜冠軍 |\n"
        "|---|---|---|\n"
        "| 單張 SOAP 摘要 | TBD | TBD |\n"
        "| 單張 DDx 推理 | TBD | TBD |\n"
        "| 中文用藥諮詢 | TBD | TBD |\n"
        "| 中文 ICD 編碼 | TBD | TBD |"
    )
    plain_new = (
        "| 維度 | 最快冠軍 | 最便宜冠軍 |\n"
        "|---|---|---|\n"
        f"{winner_rows.get('soap_en','| 單張 SOAP 摘要 | TBD | TBD |')}\n"
        f"{winner_rows.get('ddx_en','| 單張 DDx 推理 | TBD | TBD |')}\n"
        f"{winner_rows.get('drug_zh','| 中文用藥諮詢 | TBD | TBD |')}\n"
        f"{winner_rows.get('icd_zh','| 中文 ICD 編碼 | TBD | TBD |')}"
    )
    article = article.replace(plain_old, plain_new)

    # also inject MODEL_MATRIX placeholder if present (blog format uses _TBD: MODEL_MATRIX_)
    article = article.replace("_TBD: MODEL_MATRIX_", build_model_matrix_table())

    DST.write_text(article, encoding="utf-8")
    print(f"wrote {DST}")
    return 0


def build_model_matrix_table() -> str:
    return (
        "| 模型 | H200 NVL | Mac mini-class M4 32GB | 備註 |\n"
        "|---|:-:|:-:|---|\n"
        "| Qwen 3.6 35B-A3B | ✓ | ✓ | hybrid MoE，3B active |\n"
        "| Qwen3-Next 80B-A3B | ✓ | ✗ 太大 | **H200 only** 80B MoE，3B active |\n"
        "| Gemma 4 26B-A4B | ✓ | ✓ | MoE，4B active |\n"
        "| Gemma 4 31B | ✓ | ✗ 32GB OOM | **H200 only** dense 31B |\n"
        "| MedGemma 27B-text-it | ✓ | ✗ 32GB OOM | **醫療專用** dense 27B |\n"
        "| MedGemma 4B-it | ✓ | ✗ multimodal path | **醫療專用** 4B |\n"
        "| Phi-4 14B | ✓ | ✓ | dense 14B (Microsoft) |\n"
        "| Mistral Small 3.2 24B | ✓ | ✓ | dense 24B |\n"
        "| GLM 4.7-Flash | ✓ | ✗ 太大 | **H200 only** hybrid (Zhipu AI flagship) |"
    )


if __name__ == "__main__":
    sys.exit(main())
