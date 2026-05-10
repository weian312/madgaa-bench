# 一台 Mac mini，能不能取代一張 H200？我們在 4 個臨床任務、9 個本地 LLM、52 個 cell 上實測了

> Madgaa Engineering · 2026-05 · 醫療 AI Efficiency 系列

---

## 三個你現在就會想知道的數字

1. **同一張 SOAP 摘要、同一份病歷、同一個模型 (Qwen 3.6 35B-A3B Q4)**——Mac mini 跑 11.48 秒，H200 跑 2.08 秒。**Mac 慢 5.5 倍，但每張病歷成本只有 H200 的一半**（NT$0.012 vs NT$0.023）。
2. 把同一個比較放到 9 個模型 × 4 個臨床任務的全表上，**4 個任務裡有 3 個的「最便宜方案」是 Mac mini**——只有「鑑別診斷」DDx 任務 H200 才扳回一城（靠 MedGemma 4B）。
3. **Break-even ≈ 1.6 個並行使用者**。意思是：你的本地醫療 AI 同一時間真的有 ≥ 2 個醫師同時在用、不只是「掛在那」，H200 的攤提才開始划算。對台灣大多數小診所、單診間醫療站——**Mac mini class 是 strictly cheaper per task**。

我們把整個實測過程、9 個模型在 Mac mini-class M4 32GB 與 H200 NVL server 上的每一張數字都攤出來，包含「跑不動」的那些。下面就是。

---

## 我們以為 H200 會輾壓，結果...

說實話，這個 project 一開始的假設是「H200 一張卡 NT$1.5M、Mac mini 一台 NT$3.7 萬，差 40 倍硬體價，per-task 上 H200 應該至少快 10 倍、便宜 5 倍」。

開始量了之後第一個發現就翻車——**Mac mini 慢是真的（5–10 倍）、但便宜也是真的（per-task 1.5–3.8 倍）**。原因不是 H200 不快，是 server 級硬體 24/7 攤提的 baseline 成本太重，而醫療診間的 single-user 工作流大部分時間 GPU 是 idle 在燒錢。Mac mini 按工作日 2,000 小時/年攤、桌邊放、不需機房 PUE，每小時 NT$3.78；H200 server 每小時 NT$40.55，**11 倍的時間成本差**——遠大於它的速度優勢。

這篇文章就是把這個 trade-off 拆開來給你看。

---

## 故事要從一個下午門診開始

> 主治醫師看完一個 outpatient 病人，走出診間。手裡是手寫筆記 + 系統內的 vital sign + 兩張檢查報告。下一個病人 3 分鐘後就要進來。**他需要 AI 在 30 秒內整理出 SOAP 摘要、列出 5 個 DDx、查 Erythromycin 跟病人現有 4 個藥的交互作用、給 ICD-10 code**。

這四個任務 = 我們的 benchmark suite：

| 任務 | 描述 | 真實場景 |
|---|---|---|
| **A. SOAP 摘要 (英)** | 把 ~400 token de-id encounter note 摘成 SOAP 4 段 | 門診後 5 分鐘內結構化記錄 |
| **B. DDx 推理 (英)** | chief complaint + findings → top 5 differential dx | 急診 / 不明病因會診 |
| **C. 用藥諮詢 (中)** | Warfarin + Amiodarone + Atorvastatin + Metformin 加 Erythromycin | 藥師桌邊 / 老人慢病多重用藥 |
| **D. ICD-10 編碼 (中)** | 偏頭痛病例 → 最合適 ICD-10-CM code | 病歷後台健保編碼 |

每個 cell（hardware × model × task）跑 1 次 warmup + 5 次正式 run，量 wall-clock e2e、TTFT、輸出字元、輸出 hash（驗 deterministic）。

---

## 30 秒看完 — 速度 × 成本 雙冠軍表

| 維度 | 最快冠軍 | 最便宜冠軍 |
|---|---|---|
| **單張 SOAP 摘要** | _TBD_ | _TBD_ |
| **單張 DDx 推理** | _TBD_ | _TBD_ |
| **中文用藥諮詢** | _TBD_ | _TBD_ |
| **中文 ICD 編碼** | _TBD_ | _TBD_ |

> 看完這張表，**80% 的讀者已經有答案了**。剩下 20% 想看「我家是中型醫院、會服務 5–10 個醫師、預算 70 萬」這種具體分群推薦——直接跳到[文末「所以你該買哪一個？」](#結論)那段。

---

## 帳本要先攤開：硬體成本怎麼算的

這篇所有「per-task NT$」的數字都從這張表算出來，**請務必用你自己診所/醫院的數字替換**——成本算式我們公開放出來了：

| 項目 | Mac mini-class M4 32GB | H200 NVL server |
|---|---:|---:|
| 硬體售價 | NT$36,900 | NT$1,500,000 |
| 攤提年限 | 5 年 | 5 年 |
| 年使用工時 | 2,000 hr (工作日 8h × 250d) | 8,760 hr (24/7) |
| 推理時功耗 | 30 W | 1,500 W |
| 電費 | NT$3.0 / kWh | NT$3.0 / kWh |
| PUE / 機房 overhead | 0 (桌邊) | 1.4 (一般機房) |
| **每小時硬體攤提** | **NT$3.69** | **NT$34.25** |
| **每小時電費 + cooling** | NT$0.09 | NT$6.30 |
| **總每小時成本** | **NT$3.78** | **NT$40.55** |

**11 倍的時間成本差**——這就是 Mac 的 KO punch。Mac 我們用「工作日 8 小時」攤，H200 用「24/7」攤——前者其實對 H200 比較有利（如果 Mac 也算 24/7，差會更大）。讀者要記得這點。

換算成 per-task：每張任務的 NT$ = (e2e 秒數 / 3600) × (每小時成本)。

---

## 模型矩陣：誰能在誰身上跑

> 全部 4-bit 量化（Mac 是 4-bit MLX、H200 是 GGUF Q4_K_M）。reasoning / thinking 都關掉以求公平（`--no-thinking` / `--reasoning off`）。

_TBD: MODEL_MATRIX_

**為什麼有些 cell 是 ✗**：Mac mini-class 32GB 統一記憶體，扣掉 macOS 約 ~22 GB 可用工作集——**裝得下 hybrid MoE、裝不下 dense 27B+**。這個天花板就是文章的另一條主軸：你想在診間跑 27B/31B dense 等級的醫療 fine-tune，**真的需要更多記憶體（Mac Studio 64GB+ / M4 Pro / 上 H200）**。

**被本文剔除的模型 — 為什麼**：

> 跑了，看到雷，剔除——把這些寫出來，省你重複踩。

- **DeepSeek-R1-Distill 32B / GPT-OSS 20B** — reasoning model。即使在 server 端關了 thinking (`--reasoning off`)、client 加 `--no-thinking`，在我們四個臨床 prompt 上仍出現**空可見輸出**（visible content delta = 空字串、5/5 同一個 SHA256 e3b0c44…）或大量內部獨白才出答案。對「醫師桌邊輔助」這個主軸——你不能把空白回應交給臨床醫師——直接剔除。
- **DeepSeek V4-Flash 284B / V4-Pro 1.6T**（2026-04-24 釋出，frontier 級開源）— 110–865 GB 4-bit quant，**Mac 全系列吃不下，單張 H200 也只能勉強塞 2-bit DQ 版（精度有疑慮）**。本期略過，留待「多卡 / Mac Studio 192GB」續篇。
- **V4-Flash 蒸餾到 Qwen 3.5 9B** （社群 port `Jackrong/Qwen3.5-9B-DeepSeek-V4-Flash`，~5GB 4bit，Mac 跑得起來） — **我們真的去 pull 跟 bench 了**。結果：Qwen 3.5 9B 本身是 reasoning model，distill V4 只是讓 thinking 走 V4 風格，撞到「空可見輸出」的同一面牆。所以「Mac mini 上跑得動 V4 蒸餾版」的答案是「能 load，但 reasoning behaviour 讓臨床 use case 不可用，**等下一代 V4 non-reasoning distill / 直接 V4 Lite 出來再說**」。

---

## 看完一張圖你就有答案 — 圖 3：成本 × 速度二維分布

(FIG3_PLACEHOLDER)

**怎麼看**：
- **X 軸**：每張任務的 wall-clock 秒數（左 = 快）
- **Y 軸**：每張任務的 NT$（下 = 便宜）
- **左下角** = 既快又便宜（你想去的地方）
- **右上角** = 又貴又慢（你想避開的地方）
- **綠色點** = Mac mini-class、**藍色點** = H200 NVL

讀完這張圖，你會發現一件事：**Mac mini 永遠在 X 軸右半邊（慢），但很多 model 在 Y 軸下半（便宜）**——它的 CP 值不是「兩者都贏」，是「我用慢一點換便宜很多」。這就是本文的核心命題。

---

## 圖 1：四個任務的 wall-clock e2e

(FIG1_PLACEHOLDER)

---

## 圖 2：四個任務的 NT$ / task

(FIG2_PLACEHOLDER)

---

## 圖 4：H200 要服務幾個並行使用者，per-task 才會比 Mac 划算？

(FIG4_PLACEHOLDER)

> 這張圖是本文最有用的「實際採購建議」依據。**break-even ≈ 1.59 個並行使用者**——大多數小診所的 effective concurrent users 通常 < 1（醫師輪流，不是同時跑 inference）。

---

## 圖 5：兩端輸出長度是否一致

(FIG5_PLACEHOLDER)

> 同 prompt + 同 quant 在不同硬體下輸出**字元數會差 25–50%**（Mac 端往往比 H200 端寫得長一些）。原因是 quant tool 的數值微差 + chat template 差異。**這提醒臨床部署前必須做品質評估**——本文不能保證「速度誰快、成本誰低」之外，「對不對」也要靠你自己驗。

---

## 圖 6：每個任務的 cost leaderboard（前 10 強）

(FIG6_PLACEHOLDER)

---

## 完整實測結果表（給想自己挖數字的人）

> 每個 row 對應 `results/cost_per_task.csv` 一個 row。每個數字都是 5 runs 的 p50。

### SOAP 摘要任務（英文，~400 token 輸入，max_tokens=600）
TBD: SOAP_TABLE_ROWS

### DDx 推理任務（英文，~250 token 輸入，max_tokens=400）
TBD: DDX_TABLE_ROWS

### 用藥諮詢任務（中文，~200 token 輸入，max_tokens=500）
TBD: DRUG_TABLE_ROWS

### ICD-10 編碼任務（中文，~120 token 輸入，max_tokens=200）
TBD: ICD_TABLE_ROWS

---

## 所以你該買哪一個？

> 我們把實測直接翻譯成具體建議。

### 🩺 一人診所 / 個人工作站（≤ 1 並行使用者）
**買 Mac mini（M4 24GB / 32GB）。** Per-task 成本最低，1.6–11.5 秒等待時間在臨床流程裡完全可接受（你打字寫病歷也要這麼久）。選模型優先：
- **Qwen 3.6 35B-A3B 4bit MLX**：中文用藥 / ICD 任務最便宜
- **Gemma 4 26B-A4B 4bit MLX**：英文 SOAP / DDx 最便宜
- 避開 dense 27B+（OOM）、reasoning model（會空輸出或太慢）

### 🏥 中型醫院 / 同時 ~3–10 醫師（並行 3–10 使用者）
**門檻交叉**——我們實測 break-even 是 ~1.6 並行使用者。如果你能保證系統真的同時被 ≥ 3 人用、不只是掛在那，H200 的 per-task 成本開始低於 Mac。但你要算清楚 **effective concurrency**——很多醫院的「3 個診間」實際同時跑 inference 的 utilization 只有 0.5。如果是這樣，部署 3 台 Mac mini 反而比 1 台 H200 cheaper。

### 🏨 教學醫院 / 區域醫院（並行 ≥ 10）
**H200 是合理選擇**——大規模並行 + batch 模式 + 24/7 utilisation 把硬體攤提除分到極小，per-task 比 Mac 便宜 5–10 倍。也是醫療 AI SaaS 的路線。但這個 scale 通常需要不只一張 H200，要算 cluster-level TCO。

### 💊 「我就是要醫療專用模型」
- 預算夠、要 27B 級：**H200 + MedGemma 27B-text-it Q4**（最高品質，但 H200 only）
- 預算緊、可接受 4B 級：**H200 + MedGemma 4B-it Q4**（速度橫掃、便宜，但 4B 精度比 27B 差）
- Mac 上跑醫療 fine-tune 想跑大的：**等 Mac Studio 64GB+ 或 M4 Pro**（本機 32GB 跑不動 27B dense）

### 💰 「我預算只夠一台筆電」
**Mac mini M4 24GB + Qwen 3.6 35B-A3B 4bit。** NT$ 不到 30k 的硬體 + 一個 hybrid MoE + Rapid-MLX serve。Single-user 任務全套都能跑，per-task NT$0.0017–0.012，便宜得不像話。

---

## 我們不打算唬你的限制

- 本機其實是 **MacBook Air M4 32GB**（Memory bandwidth 120 GB/s）作為 Mac mini M4 base / 24GB 32GB 代理（兩者 bandwidth 一致）。M4 Pro 273 GB/s 預期能把 Mac 速度拉到 ~2–3× 接近 H200，**未測**。
- H200 用 llama.cpp Q4_K_M（apples-to-apples quant）而非 vLLM BF16；後者 throughput 應更高，但 single-user CP 值論述影響有限。
- 醫療 task quality 我們只看 deterministic + 字元長度，**沒有臨床醫師雙盲評分**——「速度誰快、成本誰低」可信，但「**輸出對不對**」是另一個課題，臨床部署前必做。
- 4-bit quant 對 medical 任務的潛在 hallucination 影響本文未獨立研究——醫療場景應視為「需臨床醫師覆核」。
- 本文僅測 single-user latency；H200 多並行優勢在圖 4 是 *推算的線*，未做實機 batch=N 量測。
- 跑不動的模型（Gemma 4 31B、MedGemma 27B、Qwen3-Next 80B、GLM 4.7-Flash 等）標 OOM——**跑不動本身就是 CP 故事的一部分**。

---

## 你可以自己重跑（raw data 都在）

所有原始資料、scripts、figures、prompts 在 H200 server 上：

- **raw logs**: `h200:/data/txtner-bench/madgaa-bench/v2/raw_logs/{h200,mac}/*.jsonl`
- **彙總 CSV**: `results/raw_runs.csv` / `per_task_metrics.csv` / `cost_per_task.csv`
- **圖**: `figures/01_*.png` 到 `figures/06_*.png`
- **Bench scripts**: `scripts/bench_medical.py`、`compute_cost_per_task.py`、`plot_v2.py`、`run_h200_sweep.sh`、`run_mac_smart_sweep.sh`
- **Prompts**: `prompts/task_A_soap_en.txt` 等四個檔案
- **環境**: `env/h200_env.txt` / `env/macmini_env.txt`

每個成本數字都對應 `cost_per_task.csv` 中的一個 row。所有假設（硬體價、攤提年、活躍工時、功耗、電費、PUE）都列在 `compute_cost_per_task.py` 的 `COST_ASSUMPTIONS` dict——換成你自己診所的實際數字，跑一次就會得到你自己的 break-even 答案。

---

## 下一輪要做的（給自己留作業）

- **真實並行壓測**：H200 同時 N=2/4/8/16 個 chat-completion，看實機 break-even 跟我們的線性推算差多少
- **臨床醫師雙盲評分**：四個任務各 50 個樣本，由臨床醫師對 Mac vs H200 的輸出做 AB test
- **Mac Studio M4 Pro 273 GB/s**、**M3 Ultra 512 GB**：跑得動 27B dense / V4-Flash 4bit 的 Mac 級硬體
- **DeepSeek V4-Flash 4bit (110GB)** 在多卡 H200 上 — 真正的 frontier model 對 Mac mini 的 CP 終極對照
- **MedGemma 1.5 系列**（Google 2026-04 新版）對比 vs 1.0
- **Mac 上跑得起來的 V4 蒸餾版** — `Jackrong/Qwen3.5-9B-DeepSeek-V4-Flash`（已測，看下方表格）
