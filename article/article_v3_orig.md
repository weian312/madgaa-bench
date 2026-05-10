# 醫療 AI 本地推理大比拼：9 個開源模型 × 4 個臨床任務 × Mac mini vs H200，誰是 CP 值之王？

> Madgaa Engineering · 2026-05 · 醫療 AI Efficiency 系列

## 最強發現（30 秒看完）

> 我們在同一份 SOAP 摘要 / DDx / 用藥諮詢 / ICD 編碼任務上，把 9 個 4-bit 量化的本地 LLM 跑在 **MacBook Air M4 32GB**（Mac mini-class）和 **H200 NVL server** 上，**最讓我們意外的結論是這個**：

**TBD: HEADLINE_FINDING_TO_BE_FILLED**

換句話說——

- **single-user 醫療診間** → MAC_BEST_MODEL 是首選（Mac mini 1 台 ~NT$36,900）
- **同時服務 ≥ 2 醫師** → H200 + H200_BEST_MODEL（per-task 才開始比 Mac 便宜）
- **要醫療專用 fine-tune** → MEDICAL_BEST_MODEL（H200 only，因為 Mac mini 32GB 跑不動 27B dense）
- **完整分群結論**請看文末「結論：你應該買哪個」

---

## TL;DR — 速度 × 成本 雙冠軍

| 維度 | 最快冠軍 | 最便宜冠軍 |
|---|---|---|
| 單張 SOAP 摘要 | TBD | TBD |
| 單張 DDx 推理 | TBD | TBD |
| 中文用藥諮詢 | TBD | TBD |
| 中文 ICD 編碼 | TBD | TBD |

**Mac vs H200 break-even（Qwen3.6-35B-A3B Q4 為基準）**：約 1.94 個並行使用者——也就是說，**只要你的本地醫療 AI 不會同時被 2 人用，Mac mini 就是 per-task 成本最低的選擇**。

---

## 為什麼寫這篇

「我家診所 / 醫院要不要花錢買 H200」這個問題我們半年內被問了三次。每次都是同一句反問——你的工作量是多少？同時服務幾個醫師？

這篇文章把那個反問拆開、量化。我們選了 **9 個開源 LLM**（Qwen 3.6 / Qwen3-Next / Gemma 4 系列 / MedGemma 醫療專用 / Phi-4 / Mistral Small / GLM 4.7-Flash）在四個典型臨床任務上實測，每端硬體跑 1 次 warmup + 5 次正式 run，記錄 wall-clock e2e、輸出字元數、輸出 hash（驗 deterministic）。每張結果都附 raw_runs.csv 的 run_id 可追溯。

文章前面是「最強的講哪個」，後面附上完整 9 model × 4 task × 2 hardware 的對照表（不是每個 cell 都跑得起來——Mac 32GB 有些 dense 大模型跑不動，這也是文章的一部分）。

> **被本文剔除的模型**：DeepSeek-R1-Distill-32B 與 GPT-OSS 20B 雖然有 4-bit 量化版可在我們硬體上跑，但都是 reasoning model，即使 `--reasoning off` / `--no-thinking` 在我們的醫療 prompt 上仍出現空輸出或大量 `<think>` 內部獨白後才出視可見內容；對「臨床醫師桌邊輔助」這個主軸不貼，剔除以避免雜訊。DeepSeek V4-Flash (284B)、V4-Pro (1.6T) 雖是 2026-04 釋出的最新 frontier 模型，但 110-160GB+ 規模在 Mac mini-class 完全跑不動、單張 H200 也只能勉強塞 2-bit 版，**不適合「Mac mini CP 值」這個敘事**，留待未來多卡 / Mac Studio 文章。

---

## 任務設計

| Task | 描述 | 輸入長度 | max_tokens |
|---|---|---:|---:|
| **A. SOAP 摘要** (英) | 把 ~400 token 的 outpatient encounter note 摘成 SOAP-format | ~400 | 600 |
| **B. DDx 推理** (英) | 由 chief complaint + findings 列前 5 個鑑別診斷 | ~250 | 400 |
| **C. 用藥諮詢** (中) | Warfarin + Amiodarone + Atorvastatin + Metformin 加 Erythromycin 的交互作用 | ~200 | 500 |
| **D. ICD-10 編碼** (中) | 簡述偏頭痛 → ICD-10-CM code | ~120 | 200 |

四個任務涵蓋：(1) 結構化摘要、(2) 推理、(3) 中文藥理、(4) 短輸出編碼——本地醫療 AI 的「90% 真實工作」。

---

## 硬體假設（透明，可重算）

| 項目 | Mac mini-class M4 32GB | H200 NVL server |
|---|---:|---:|
| 硬體 | NT$36,900 | NT$1,500,000 |
| 攤提年限 | 5 年 | 5 年 |
| 年使用工時 | 2,000 hr (工作日 8h × 250d) | 8,760 hr (24/7) |
| 推理時功耗 | 30 W | 1,500 W |
| 電費 | NT$3.0 / kWh | NT$3.0 / kWh |
| PUE / 機房 overhead | 0 (桌邊) | 1.4 (一般機房) |
| **每小時硬體成本** | **NT$3.69** | **NT$34.25** |
| **每小時電費 (含 PUE)** | NT$0.09 | NT$6.30 |
| **總每小時成本** | **NT$3.78** | **NT$40.55** |

**11 倍**——H200 server 每小時成本是 Mac 的 11 倍。本文每張 task 的 NT$ 都用這個假設算。讀者用自己診所/醫院的實際數字替換 `compute_cost_per_task.py` 中的 `COST_ASSUMPTIONS` dict 就會得到自己的答案。

---

## 模型矩陣（本次實測）

> 全部 4-bit 量化（Mac 為 4-bit MLX、H200 為 GGUF Q4_K_M），thinking / reasoning 都關閉以求公平。

| 模型 | Mac 端 | H200 端 | 類型 / 用途 |
|---|:---:|:---:|---|
| Qwen 3.6 35B-A3B | ✓ | ✓ | hybrid MoE，3B active |
| Qwen3-Next 80B-A3B | ✗ (太大) | ✓ | **H200 only** 80B MoE，3B active |
| Gemma 4 26B-A4B | ✓ | ✓ | MoE，4B active |
| Gemma 4 31B | ✗ (32GB OOM) | ✓ | **H200 only** dense 31B |
| MedGemma 27B-text-it | ✗ (32GB OOM) | ✓ | **醫療專用** dense 27B |
| MedGemma 4B-it | ✗ (mlx-vlm path) | ✓ | **醫療專用** multimodal 4B |
| Phi-4 14B | ✓ | ✓ | dense 14B (Microsoft) |
| Mistral-Small 3.2 24B | ✓ | ✓ | dense 24B |
| GLM 4.7-Flash | ✗ (太大) | ✓ | **H200 only** hybrid (Zhipu AI flagship) |

---

## 圖 1：本次測試所有 (Hardware × Model × Task) 的 wall-clock e2e

![Fig 1 — wall-clock e2e per task / model / hw](FIG1_PLACEHOLDER)

(圖一視覺重點)

---

## 圖 2：對應的 NT$ / task

![Fig 2 — NTD per task](FIG2_PLACEHOLDER)

(圖二視覺重點)

---

## 圖 3：成本 × 速度 二維分布

![Fig 3 — cost vs e2e 2D scatter](FIG3_PLACEHOLDER)

理想是「左下」（既快又便宜），TBD: WHO_SITS_AT_LEFT_BOTTOM。

---

## 圖 4：H200 break-even 曲線（多並行才划算）

![Fig 4 — break-even concurrency](FIG4_PLACEHOLDER)

H200 只在 ≈ 1.94 個並行使用者後才開始 per-task 比 Mac 便宜。

---

## 圖 5：兩端輸出長度對比（quality 代理）

![Fig 5 — output size consistency](FIG5_PLACEHOLDER)

同 prompt + 同 quant 在不同硬體下的字元差距，提醒「同模型在不同 quant 工具下不是 byte-identical」。

---

## 完整實測結果表

> 以下表格 row by row 對應 `results/cost_per_task.csv`。每個數字都是 5 runs 的 p50。

### 表 1：SOAP 摘要任務（英文，~400 token 輸入，max_tokens=600）

| Hardware | Model | e2e (s) | output (chars) | NT$ / task | 備註 |
|---|---|---:|---:|---:|---|
TBD: SOAP_TABLE_ROWS

### 表 2：DDx 推理任務（英文，~250 token 輸入，max_tokens=400）

| Hardware | Model | e2e (s) | output (chars) | NT$ / task | 備註 |
|---|---|---:|---:|---:|---|
TBD: DDX_TABLE_ROWS

### 表 3：用藥諮詢任務（中文，~200 token 輸入，max_tokens=500）

| Hardware | Model | e2e (s) | output (chars) | NT$ / task | 備註 |
|---|---|---:|---:|---:|---|
TBD: DRUG_TABLE_ROWS

### 表 4：ICD-10 編碼任務（中文，~120 token 輸入，max_tokens=200）

| Hardware | Model | e2e (s) | output (chars) | NT$ / task | 備註 |
|---|---|---:|---:|---:|---|
TBD: ICD_TABLE_ROWS

---

## 結論：你應該買哪個

> 我們把實測翻譯成具體建議：

### 一人診所 / 個人工作站（≤ 1 並行使用者）
TBD

### 中型醫院 / 同時 ~3-10 醫師（並行 3-10 使用者）
TBD

### 教學醫院 / 區域醫院（並行 ≥ 10）
TBD

### 「我就是想跑醫療專用模型」
TBD

### 「我預算只夠一台筆電」
TBD

---

## 限制與透明度

- 本機 Mac 是 MacBook Air M4 32GB（Memory bandwidth 120 GB/s）作為 Mac mini M4 24/32GB 代理；M4 Pro 273 GB/s 預期會把 Mac 速度拉到 ~2-3× 接近 H200，未測
- H200 端用 llama.cpp Q4_K_M (apples-to-apples quant) 而非 vLLM BF16；後者 throughput 應更高，但 single-user CP 值論述影響有限
- 醫療 task 的 quality 我們只看 deterministic + 字元長度，**沒有臨床醫師雙盲評分**；意思是「速度誰快、成本誰低」可信，但「**輸出對不對**」是另一個課題，臨床部署前必做
- 4-bit quant 對 medical 任務的潛在 hallucination 影響本文未獨立研究——醫療場景應視為「需臨床醫師覆核」
- 本文僅測 single-user latency；H200 多並行優勢在圖 4 是 *推算的線*，未做實機 batch=N 量測
- Mac 跑不動的模型（Gemma 4 31B、MedGemma 27B、Qwen3-Next 80B）標 OOM，不是「跑得慢」——跑不動才是真實 CP 值故事的一部分

---

## 可重現性

所有 raw data / scripts / figures 在 H200 server 上：

- raw logs：`/data/txtner-bench/madgaa-bench/v2/raw_logs/{h200,mac}/*.jsonl`
- 聚合資料：`results/raw_runs.csv` / `per_task_metrics.csv` / `cost_per_task.csv`
- 圖表：`figures/01_*.png` 至 `figures/05_*.png`
- 跑分腳本：`scripts/bench_medical.py` / `compute_cost_per_task.py` / `plot_v2.py`
- 批次 sweep 腳本：`scripts/run_mac_sweep.sh` / `scripts/run_h200_sweep.sh`
- prompts：`prompts/task_A_soap_en.txt` 等四個檔案
- 環境：`env/h200_env.txt` / `env/macmini_env.txt`

每個成本數字都對應 `cost_per_task.csv` 中的一個 row。所有假設（硬體價、攤提年、活躍工時、功耗、電費、PUE）都列在 `compute_cost_per_task.py` 的 `COST_ASSUMPTIONS` dict——換成你的實際數字，跑一次就會得到你自己的成本。

---

## 下一輪要驗的實驗

- 真實並行壓測：H200 同時 N=2/4/8/16 個 chat-completion，看實機 break-even 跟我們的線性推算差多少
- 臨床醫師雙盲評分：四個任務各 50 個樣本，由臨床醫師對 Mac vs H200 的輸出做 AB test
- M4 Pro / M4 Max Mac mini Studio 上重跑 — 273 GB/s bandwidth 預期會把 Mac 速度拉到 2-3× 接近 H200
- vLLM 在 H200 上 BF16 + speculative decoding — 看 throughput 上限到哪
- MedGemma 1.5 系列（Google 2026-04 釋出）對比 vs MedGemma 1.0
- Mac MedGemma 4B multimodal pathway 設定（mlx-vlm 已裝完，下次補實測）
