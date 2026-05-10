# Blog Agent Runbook — Madgaa Engineering

> 把「人類審視一次後就能放出去」的標準寫死。任何 agent 在 Madgaa 部落格上做事，先讀這份。

這份 runbook 是 [v2 系列](https://madgaa.com/blog/p/medical-ai-9-models-mac-vs-h200-cp-value-blog-2026-05?lang=zh) 從 0 ship 到 5-part 系列的踩坑紀錄濃縮版。把 26 個曾經讓「整個版面炸掉」的雷點寫成 agent 自動處理流程 + admin 一眼可審清單。

## 工作流程

```
[contributor 上傳素材]
    ↓
[blog-author agent 處理] —— 讀本 runbook
    ↓
[blog-render agent 自我 audit] —— 跑 R-A1..R-A8 lints
    ↓
[admin 後台預覽] —— 看渲染後 + audit 結果
    ↓
[一鍵 publish 系列]
```

Agent 階段對應的腳本 / 資源：
- `blog-author`: 把素材切成 3-5 part 系列、套 R-S1..R-S6 結構規則、生成 zh + en 雙語、選 hero / 排 figure / 上傳 asset bundle / 生成可選 demo video
- `blog-render`: 對每篇跑 R-A1..R-A8 audit、產出 admin 可見報告
- `admin preview`: 後台同時看 5 篇 rendered preview + audit 報告 + 一鍵 publish all

## 麻煩了 26 次的雷（按發生順序）

每條後面都有 Rule ID，agent 用 ID 反查防雷。

### 解析器雷（Madgaa 自己的 parseArticleBlocks）

1. **`**bold**` 不會被解析** — Rule **R-P1**
2. **`[link](url)` 不會被解析** — Rule **R-P2**
3. **markdown table 不會被解析** — Rule **R-P3**
4. **\`code\` inline 不會被解析** — Rule **R-P4**
5. **`---` 變成字面 hr 字串** — Rule **R-P5**
6. **standalone `![alt](url)` image 沒處理** — Rule **R-P6**
7. **`splitInlineHeading` 把中文段落第一個 token 拆成 H2**（"如果你能保證..." 整段被切爛）— Rule **R-P7**
8. **數字開頭段落 `1. 解壓...` 變 H2 大 block** — Rule **R-P8**
9. **多行 blockquote 第二行 `>` 沒被剝掉** — Rule **R-P9**

### Asset / 後端雷

10. **blog asset 只接受 kind=image / video，下載 tar.gz 拿不到** — Rule **R-A-K1**（已 patch backend allowlist 加 `other`）
11. **`/api/blog/assets/<uuid>` 沒附副檔名 → `<video>` markdown 偵測不到 .mp4** — Rule **R-A-K2**（用 `![video: caption](url)` 自訂 syntax）
12. **assets 路徑 `/api/blog/assets/<id>` 限 published post 才返回 200** — Rule **R-A-K3**

### 視覺雷

13. **hero h1 用 `font-black` (900) + tracking [-0.075em] 太醜，5 行包覆** — Rule **R-V1** → font-semibold (600) + tracking [-0.025em]
14. **body H2 用 `font-black` 過粗** — Rule **R-V2** → font-bold (700)
15. **`fig01_e2e_per_task.png` legend 列了 Mac+MedGemma 27B（OOM cell），bar 為 0** — Rule **R-V3** → 過濾 "✗" cells
16. **fig04 break-even 文字 1.6 跟 article body 5.5 不同步**（cost CSV 改了沒重畫）— Rule **R-V4** → 改 cost 必同步重畫圖
17. **figure 不能點放大**（`<img>` 沒包 `<a target="_blank">`）— Rule **R-V5**
18. **video 盒子 caption 字幕直接在影片裡，截斷顯示** — Rule **R-V6** → 真實字數從 `output_chars` 不從 `len(output_text)`

### 內容 / 邏輯雷

19. **「Mac 用 8h × 250d、H200 用 24/7」非對稱攤提**（讀者 "下班是會關機？"）— Rule **R-C1** → 兩端同條件、24/7 對稱攤提
20. **Mac config label 32GB 但用 NT$36,900 攤、卻又同時推薦給讀者 48GB** — Rule **R-C2** → 把「測試 hardware」跟「推薦 hardware」分清楚
21. **Cost 表用 NT$36,900 / 8h 攤 = NT$3.78/hr**（大幅低估 Mac 優勢）— Rule **R-C3** → 改 NT$54,900 / 24/7 = NT$1.34/hr
22. **break-even 用 first qwen match → 抓到 Qwen3-Next 80B 不是 Qwen 3.6 35B-A3B** — Rule **R-C4** → filter 寫精準
23. **Article 引用 `cost_per_task.csv` 但讀者拿不到** — Rule **R-C5** → 每個 dataset / script 都要有公開連結
24. **「下一期會做 public repo」是空頭支票** — Rule **R-C6** → 不能 ship 才寫保證
25. **內部 prompt 是策展案例**（讀者懷疑 cherry-pick）— Rule **R-C7** → 必有公開資料集 cross-validation（MTSamples 是醫療類 default）
26. **Framework 軸只測一邊**（Mac=Rapid-MLX, H200=llama.cpp Q4，Google 推薦的 transformers BF16+MTP 沒測）— Rule **R-C8** → 框架軸至少兩條跑出 head-to-head 數字

## R-S 結構規則（series + part 之間）

- **R-S1** — 文章 > 1500 字必切系列。每篇 600-1200 字、自帶 hook + takeaway。
- **R-S2** — 系列每篇必有 ← 上一篇 / 下一篇 → 導覽（首篇沒上、末篇沒下）。
- **R-S3** — 系列共用 hero + backdrop（視覺一致性）。但每篇有自己的 excerpt（不是 paraphrase 上一篇）。
- **R-S4** — 系列首篇放 hook + 30 秒可看完版本；末篇放限制 / 跨驗證 / 開源說明。
- **R-S5** — slug 規範：`<topic>-<n>-<short>`，例：`mac-vs-h200-2-cost-accounting`。第 1 篇可保留 legacy slug。
- **R-S6** — 末篇的「下一篇 →」連結若指向尚未發布的 part，先 publish 再 cross-link。

## R-A audit 清單（render agent 跑 / admin 預覽看）

每個 audit 失敗都列在 admin 預覽頁的 audit panel，紅 = block publish、橘 = warn but allow、綠 = ok。

- **R-A1 [紅]** — body innerText 含 `**xxx`（bold leak）
- **R-A2 [紅]** — body innerText 含字面 `\n> ` 多行 quote leak
- **R-A3 [紅]** — body innerText 含字面 `---`（hr leak）
- **R-A4 [紅]** — body 含字面 `PLACEHOLDER` / `TBD:` / `_TBD_`
- **R-A5 [紅]** — 引用了任何 `h200:/data/...` 私有路徑
- **R-A6 [橘]** — H1 標題 > 30 字（hero 會 7 行包覆）
- **R-A7 [橘]** — figure 沒有 `<a>` 包 `<img>`（不能點放大）
- **R-A8 [橘]** — 文中提到 `.csv` / `.py` / `.jsonl` 但沒 inline link 到 github / bundle
- **R-A9 [綠]** — 數字一致性：每個 NT$X 必對應 cost_per_task.csv 的 row（人工確認）
- **R-A10 [綠]** — 數據來源公開：使用了公開資料集（MTSamples 等），或在限制段標明內部 prompt

## R-V 視覺規則

- **R-V1** — Hero h1: `font-semibold leading-[1.1] tracking-[-0.025em]`，最多 28 字
- **R-V2** — Body H2/H3: `font-bold` 不用 `font-black`
- **R-V3** — figures：legend 動態剔除 OOM cells；不要畫零值 bar
- **R-V4** — 改 `COST_ASSUMPTIONS` 必同時 regen `compute_cost_per_task.py` + `plot_v2.py`
- **R-V5** — 所有 inline figure 包 `<a target="_blank" rel="noopener noreferrer">` 點圖開原圖
- **R-V6** — Demo video（如果有）：用 `output_chars` 不用 `len(output_text)`（v2 raw_logs `output_text` 會被 max_tokens 截斷）；caption 字幕在 figure caption 不在影片內

## R-C 內容規則

- **R-C1** — 比較 Mac vs server hardware：兩端必須同條件攤提（建議 24/7 5 年）
- **R-C2** — 「測試 hardware」 vs 「推薦給讀者的 hardware」必有顯眼 callout 分清楚
- **R-C3** — Mac 推薦配置：Mac mini M4 Pro 48GB（NT$54,900 base 2026-05）— 桌邊 0 PUE、24/7 → hourly NT$1.34
- **R-C4** — 任何 filter / lookup 把 model name 寫精準（"qwen3.6" vs "qwen"）
- **R-C5** — 每個 dataset / script / asset 必有公開連結（github / blog asset / HF dataset）
- **R-C6** — 不寫做不到的承諾。要寫「下一期會做」必先 ship。
- **R-C7** — 醫療 / 臨床類文章必須做公開資料集 cross-validation。MTSamples 是首選（Apache-2.0 / 4978 transcribed reports / [HF](https://huggingface.co/datasets/harishnair04/mtsamples)）
- **R-C8** — Framework 軸至少測 2 條跑 head-to-head（不能只 narrate 一邊）

## 系統架構提案 — 4 階段

### Phase 1（已完成）— Parser + render fixes

- 5 個 parser patch（R-P1..R-P9）已 ship
- 圖點放大已 ship（R-V5）
- 後端 asset kind=other allowlist 已 ship（R-A-K1）
- video markdown 自訂 syntax 已 ship（R-A-K2）

### Phase 2（建議下一步）— Admin audit panel

把 R-A1..R-A8 寫成 client-side script，掛在 `/blog/preview/[id]` 頁面右側。掃 rendered DOM、列出每條 lint 結果、紅 / 橘 / 綠 標記。Admin 一眼看完、按「修正後重新 audit」 / 「approve」按鈕。

`backend/modules/blog/audit.py` 負責伺服端 audit（內容檢查），`/blog/preview/[id]/AuditPanel.tsx` 負責 client-side DOM lint。

### Phase 3 — Series preview

`/blog/preview/series/[parent-slug]` 把同 series 的多篇 post 並排 preview。每篇折疊，admin 點開展開看渲染。可顯示「上下篇連結正確 / 缺失」狀態。

`blog_posts` table 加 `series_parent_slug`、`series_index` 欄位（或用 metadata）。

### Phase 4 — Author agent

把 `compose_draft` route 升級為「`compose_series`」：
- 輸入：submission body + 附加 assets（CSV / images / raw_logs / scripts）
- 輸出：3-5 個 blog_posts（draft），每篇有 hero、excerpt、body_zh、body_en、cross-links

Agent system prompt 必引用本 runbook（特別是 R-S1..R-S6、R-C1..R-C8）。

Author agent 需要的能力：
- 跑 `gen-image` skill 生成 hero（如果 contributor 沒給）
- 跑 `compute_cost_per_task.py`-style aggregation（如果輸入是 raw_logs）
- 跑 `plot_v2.py`-style figure generation
- 跑 demo video synth（如果適合）
- 上傳所有 assets 到 blog_assets table

### Phase 5（選配）— 一鍵 publish

Admin queue 頁加「publish series」按鈕。檢查所有 part 的 audit 都綠燈才能按。按下後 batch UPDATE 全部 status → published、設 published_at = now()。

## 給接手 agent 的最小 checklist

開始任何 article work 之前，至少做這 5 件事：

1. `git pull` 拉本 runbook
2. 確認你做的事屬於哪個 Rule（沒對應的 Rule 表示你在做新雷，記得寫下來）
3. 至少 ship 1 個公開 cross-validation 資料集 + 1 個公開 repo / bundle
4. ship 之前用 Chrome MCP 跑完整篇 audit（人工跑 R-A1..R-A8，未來 Phase 2 會自動）
5. 改 COST_ASSUMPTIONS 必 regen 所有 figure；改 model registry 必 regen 所有 per-task table

## 版本

| 版本 | 日期 | 主要更新 |
|---|---|---|
| 1.0 | 2026-05-10 | v2 系列 ship 後總結：26 雷 + 4 階段架構提案 |
