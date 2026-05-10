"""Generate v2 figures from results/cost_per_task.csv and results/raw_runs.csv.

Output:
  figures/01_e2e_per_task.png         — bar chart, 4 tasks × (Mac + H200) × (Qwen + MedGemma)
  figures/02_cost_per_task.png        — same layout, NTD per task
  figures/03_cost_vs_e2e_2d.png       — scatter: x=e2e (s), y=NTD per task; mac vs h200
  figures/04_break_even_concurrency.png — at what concurrency level does H200 become cheaper than Mac?
  figures/05_quality_consistency.png  — output_chars per (hw, model, task), shows whether outputs are
                                        comparable in length/structure across hardware
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa
import matplotlib.pyplot as plt  # noqa
import matplotlib.ticker as mtick  # noqa


def _ensure_cjk_font():
    candidate_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    for path in candidate_paths:
        if Path(path).exists():
            try:
                fm.fontManager.addfont(path)
                family = fm.FontProperties(fname=path).get_name()
                plt.rcParams["font.family"] = family
                plt.rcParams["axes.unicode_minus"] = False
                return family
            except Exception:
                continue
    return None


_ensure_cjk_font()


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RES = ROOT / "results"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)


def load(name: str) -> list[dict]:
    p = RES / name
    if not p.exists():
        return []
    with p.open() as fh:
        return list(csv.DictReader(fh))


def fnum(v, default=None):
    try:
        return float(v) if v not in ("", None, "None") else default
    except (TypeError, ValueError):
        return default


HW_COLOR = {
    "macmini-m4-32gb": "#06b27d",
    "h200-nvl": "#3a6dff",
}
HW_LABEL = {
    "macmini-m4-32gb": "Mac mini-class (M4 32GB)",
    "h200-nvl": "H200 NVL server",
}
MODEL_HATCH = {}  # not used in v3 multi-model figs

MODEL_NORMALISE = {
    "qwen3.6-35b-a3b": "Qwen 3.6 35B-A3B",
    "qwen3.6-35b-a3b-q4_k_m": "Qwen 3.6 35B-A3B",
    "qwen3.6-35b": "Qwen 3.6 35B-A3B",
    "qwen3.6-35b-a3b-4bit": "Qwen 3.6 35B-A3B",
    "qwen3-next-80b-a3b": "Qwen3-Next 80B-A3B",
    "gemma-4-26b-a4b-it": "Gemma 4 26B-A4B",
    "gemma-4-26b-a4b-it-4bit": "Gemma 4 26B-A4B",
    "gemma-4-31b-it": "Gemma 4 31B",
    "medgemma-27b-text-it": "MedGemma 27B",
    "medgemma-27b-text-it-4bit": "MedGemma 27B",
    "medgemma-4b-it": "MedGemma 4B",
    "medgemma-4b-it-4bit": "MedGemma 4B",
    "phi-4": "Phi-4 14B",
    "phi-4-4bit": "Phi-4 14B",
    "glm-4.7-flash": "GLM 4.7-Flash",
    "glm-4.7-4bit": "GLM 4.7-Flash",
    "gpt-oss-20b": "GPT-OSS 20B",
    "gpt-oss-20b-4bit": "GPT-OSS 20B",
    "mistral-small-3.2-24b": "Mistral Small 3.2 24B",
    "mistral-small-3.2-24b-instruct-2506-4bit": "Mistral Small 3.2 24B",
    "deepseek-r1-32b": "DeepSeek R1 Distill 32B",
    "deepseek-r1-distill-qwen-32b-4bit": "DeepSeek R1 Distill 32B",
}
TASK_LABEL = {
    "soap_en": "SOAP\n摘要(EN)",
    "ddx_en": "DDx\n推理(EN)",
    "drug_zh": "用藥諮詢\n(ZH)",
    "icd_zh": "ICD-10\n編碼(ZH)",
}
TASKS = ["soap_en", "ddx_en", "drug_zh", "icd_zh"]


def normalise_model(m: str) -> str:
    m = m.lower()
    if m in MODEL_NORMALISE:
        return MODEL_NORMALISE[m]
    for k, v in MODEL_NORMALISE.items():
        if k in m:
            return v
    return m


def fig_e2e_per_task(rows: list[dict]) -> None:
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(10, 5))
    bw = 0.18
    x = list(range(len(TASKS)))
    seen = []
    for hw_idx, hw in enumerate(["macmini-m4-32gb", "h200-nvl"]):
        for m_idx, model in enumerate(["Qwen 3.6 35B-A3B", "MedGemma 27B"]):
            heights = []
            for t in TASKS:
                v = next(
                    (fnum(r["e2e_p50"]) for r in rows
                     if r["hardware"] == hw and normalise_model(r["model"]) == model and r["task_id"] == t),
                    None,
                )
                heights.append(v if v else 0.0)
            offset = (hw_idx * 2 + m_idx - 1.5) * bw
            ax.bar(
                [i + offset for i in x],
                heights,
                bw,
                color=HW_COLOR[hw],
                hatch=MODEL_HATCH.get(model, ""),
                edgecolor="black",
                linewidth=0.5,
                label=f"{HW_LABEL[hw]} / {model}",
            )
            for xi, h in zip(x, heights):
                if h > 0:
                    ax.text(xi + offset, h * 1.02, f"{h:.1f}", ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels([TASK_LABEL[t] for t in TASKS])
    ax.set_ylabel("End-to-end wall-clock seconds (p50)")
    ax.set_title("Fig 1 — 各醫療任務的 wall-clock e2e（5 runs p50）")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "01_e2e_per_task.png", dpi=140)
    plt.close(fig)
    print("[fig01] saved")


def fig_cost_per_task(rows: list[dict]) -> None:
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(10, 5))
    bw = 0.18
    x = list(range(len(TASKS)))
    for hw_idx, hw in enumerate(["macmini-m4-32gb", "h200-nvl"]):
        for m_idx, model in enumerate(["Qwen 3.6 35B-A3B", "MedGemma 27B"]):
            heights = []
            for t in TASKS:
                v = next(
                    (fnum(r["ntd_per_task_total"]) for r in rows
                     if r["hardware"] == hw and normalise_model(r["model"]) == model and r["task_id"] == t),
                    None,
                )
                heights.append(v if v else 0.0)
            offset = (hw_idx * 2 + m_idx - 1.5) * bw
            ax.bar(
                [i + offset for i in x],
                heights,
                bw,
                color=HW_COLOR[hw],
                hatch=MODEL_HATCH.get(model, ""),
                edgecolor="black",
                linewidth=0.5,
                label=f"{HW_LABEL[hw]} / {model}",
            )
            for xi, h in zip(x, heights):
                if h > 0:
                    ax.text(xi + offset, h * 1.04, f"{h:.4f}", ha="center", fontsize=7, rotation=0)
    ax.set_xticks(x)
    ax.set_xticklabels([TASK_LABEL[t] for t in TASKS])
    ax.set_ylabel("NTD per task（含硬體攤提 + 電費 + 機房 PUE）")
    ax.set_title("Fig 2 — 各醫療任務的單次推理成本")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "02_cost_per_task.png", dpi=140)
    plt.close(fig)
    print("[fig02] saved")


def fig_cost_vs_e2e_2d(rows: list[dict]) -> None:
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(8, 6))
    for r in rows:
        hw = r["hardware"]
        e2e = fnum(r["e2e_p50"])
        cost = fnum(r["ntd_per_task_total"])
        if not e2e or not cost:
            continue
        marker = "o" if "qwen" in r["model"].lower() else "s"
        color = HW_COLOR.get(hw, "#888")
        ax.scatter(e2e, cost, marker=marker, s=120, color=color, edgecolor="black", linewidth=0.6,
                   label=f"{HW_LABEL.get(hw, hw)}/{normalise_model(r['model'])}")
        ax.annotate(
            r["task_id"], (e2e, cost),
            fontsize=7, xytext=(5, 4), textcoords="offset points",
        )
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc="upper left", fontsize=8)
    ax.set_xlabel("End-to-end wall-clock seconds (p50, lower better)")
    ax.set_ylabel("NTD per task (lower better)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title("Fig 3 — Cost × Latency 二維分佈\n（左下 = 既快又便宜；右上 = 又貴又慢）")
    ax.grid(True, which="both", linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(FIG / "03_cost_vs_e2e_2d.png", dpi=140)
    plt.close(fig)
    print("[fig03] saved")


def fig_break_even(rows: list[dict]) -> None:
    """For SOAP task on Qwen3.6 (the canonical one):
    - Mac single-user: e2e_mac, cost_mac
    - H200 single-user: e2e_h200, cost_h200
    - Assume H200 can serve C concurrent users: effective per-task cost = cost_h200 / C
    - Break-even at C* = cost_h200 / cost_mac
    """
    soap = [r for r in rows if r["task_id"] == "soap_en" and "qwen3.6" in r["model"].lower()]
    mac = next((r for r in soap if r["hardware"].startswith("mac")), None)
    h200 = next((r for r in soap if r["hardware"].startswith("h200")), None)
    if not mac or not h200:
        print("[fig04] need both mac+h200 SOAP rows; skipping")
        return
    cost_mac = fnum(mac["ntd_per_task_total"])
    cost_h200_single = fnum(h200["ntd_per_task_total"])
    if not cost_mac or not cost_h200_single:
        return
    cs = list(range(1, 33))
    h200_per_user = [cost_h200_single / c for c in cs]
    mac_per_user = [cost_mac for _ in cs]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(cs, mac_per_user, "-", color=HW_COLOR["macmini-m4-32gb"], lw=2, label=f"Mac mini, NT${cost_mac:.4f}/task")
    ax.plot(cs, h200_per_user, "-", color=HW_COLOR["h200-nvl"], lw=2,
            label=f"H200 NVL @ N concurrent users, NT${cost_h200_single:.4f}/N")
    break_even = cost_h200_single / cost_mac
    ax.axvline(break_even, color="#888", linestyle="--", lw=1)
    ax.text(break_even, max(mac_per_user[0], h200_per_user[0]) * 1.05,
            f"break-even ≈ {break_even:.1f} 並行使用者",
            ha="center", fontsize=9)
    ax.set_xlabel("假想 H200 同時服務的使用者數")
    ax.set_ylabel("每張 SOAP 摘要的 NTD")
    ax.set_yscale("log")
    ax.set_title("Fig 4 — break-even：H200 要服務幾個同時使用者，per-task 成本才會比 Mac mini 低？\n（Qwen3.6-35B-A3B Q4 / SOAP 摘要任務）")
    ax.legend(fontsize=9)
    ax.grid(True, which="both", linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(FIG / "04_break_even_concurrency.png", dpi=140)
    plt.close(fig)
    print(f"[fig04] saved (break-even = {break_even:.2f} concurrent users)")


def fig_output_size_consistency(rows: list[dict]) -> None:
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(10, 5))
    bw = 0.18
    x = list(range(len(TASKS)))
    for hw_idx, hw in enumerate(["macmini-m4-32gb", "h200-nvl"]):
        for m_idx, model in enumerate(["Qwen 3.6 35B-A3B", "MedGemma 27B"]):
            heights = []
            for t in TASKS:
                v = next(
                    (fnum(r["output_chars_mean"]) for r in rows
                     if r["hardware"] == hw and normalise_model(r["model"]) == model and r["task_id"] == t),
                    None,
                )
                heights.append(v if v else 0.0)
            offset = (hw_idx * 2 + m_idx - 1.5) * bw
            ax.bar(
                [i + offset for i in x],
                heights,
                bw,
                color=HW_COLOR[hw],
                hatch=MODEL_HATCH.get(model, ""),
                edgecolor="black",
                linewidth=0.5,
                label=f"{HW_LABEL[hw]} / {model}",
            )
    ax.set_xticks(x)
    ax.set_xticklabels([TASK_LABEL[t] for t in TASKS])
    ax.set_ylabel("輸出字元數平均（大約反映回答長度與資訊量）")
    ax.set_title("Fig 5 — 同 prompt + 同 quant，兩端輸出長度是否一致")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "05_output_size_consistency.png", dpi=140)
    plt.close(fig)
    print("[fig05] saved")


def fig_leaderboard_per_task(rows: list[dict]) -> None:
    """Top-10 combos by lowest NT$/task per task."""
    if not rows:
        return
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    for idx, t in enumerate(TASKS):
        ax = axes[idx // 2][idx % 2]
        rs = [r for r in rows if r["task_id"] == t and fnum(r["ntd_per_task_total"])]
        rs_sorted = sorted(rs, key=lambda r: fnum(r["ntd_per_task_total"]))
        rs_top = rs_sorted[:10]
        labels = [f"{HW_LABEL.get(r['hardware'], r['hardware'])[:6]}/{normalise_model(r['model'])}" for r in rs_top]
        costs = [fnum(r["ntd_per_task_total"]) for r in rs_top]
        e2es = [fnum(r["e2e_p50"]) for r in rs_top]
        colors = [HW_COLOR.get(r["hardware"], "#888") for r in rs_top]
        ypos = list(range(len(labels), 0, -1))
        ax.barh(ypos, costs, color=colors, edgecolor="black", linewidth=0.5)
        for y, c, e in zip(ypos, costs, e2es):
            ax.text(c, y, f"  NT${c:.4f} ({e:.1f}s)", va="center", fontsize=8)
        ax.set_yticks(ypos)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel("NTD per task (lower better)")
        ax.set_title(f"{TASK_LABEL.get(t, t).replace(chr(10), ' ')} — top-10 cheapest")
        ax.grid(True, axis="x", linestyle=":", alpha=0.4)
    fig.suptitle("Fig 6 — 各任務 per-task 成本前 10 強（綠 = Mac mini, 藍 = H200）", fontsize=12)
    fig.tight_layout()
    fig.savefig(FIG / "06_leaderboard_per_task.png", dpi=140)
    plt.close(fig)
    print("[fig06] saved (leaderboard)")


def main() -> int:
    cost = load("cost_per_task.csv")
    if not cost:
        print("no cost_per_task.csv yet; run compute_cost_per_task.py first")
        return 1
    fig_e2e_per_task(cost)
    fig_cost_per_task(cost)
    fig_cost_vs_e2e_2d(cost)
    fig_break_even(cost)
    fig_output_size_consistency(cost)
    fig_leaderboard_per_task(cost)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
