# benchmark_project/v2 — engineering & publishing rules

This is an **academic-style technical blog** (CP-value comparison: Mac mini vs H200 NVL on medical AI inference). When working on anything that ships from this folder — article rewrites, figures, code, blog publish — the rules below apply.

The user has had to repeat each of these. Do not make them say it again.

---

## R1 · Audit the rendered page before declaring done

Never publish or claim a layout/content change is complete without **viewing the live URL through Chrome MCP**, top to bottom.

- Use `mcp__Claude_in_Chrome__navigate` + `screenshot` (or `javascript_tool` for DOM inspection) on the actual `madgaa.com/blog/p/<slug>?lang=zh` URL.
- Scroll through the entire page. Inspect: hero, every figure, every table, every paragraph, every link.
- For tables: check `document.querySelectorAll('table').length` and confirm the count matches what you expect; verify each table's first row uses `<th>` not `<td>`.
- For markdown: regex-scan rendered `body.innerText` for leaks: `**bold**`, `[link](url)`, ` ```code``` `, raw `---`, leftover `PLACEHOLDER` strings.
- Past incident (2026-05-10): user found `用藥諮詢` + `ICD-10` tables rendering as walls of `|...|` text. Took 4 round-trips to fix. **Catch this in the audit, not after publish.**

## R2 · Default to authored HTML / structured blocks, not bare markdown

The Madgaa blog parser (`parseArticleBlocks` in `intranet-portal/src/components/blog/BlogArticleView.tsx`) is custom, minimal, and does not implement most CommonMark/GFM. We've patched it for: tables, `**bold**`, `[link](url)`, `` `code` ``, `---` skip, standalone images, `splitInlineHeading` skip-on-`**`. Anything else (footnotes, task lists, ATX `=` underlines, fenced code with language, alignment syntax) **will not render**.

- Before writing any markdown construct: confirm the parser supports it (`grep` `parseArticleBlocks`).
- For new constructs we want, default to: pre-rendered HTML in content, OR structured blocks via `articleBlocks` (`renderStructuredBlocks` in BlogArticleView).
- Per the global memory `feedback_html_layout_default.md`: when in doubt, write HTML, not markdown.

## R3 · Every dataset, script, and asset reference must be clickable

Reader-facing rule: do not mention any path or filename without giving the reader a way to actually access it.

Forbidden in article body:
- `h200:/data/...`, `madgaa@server:...`, internal SSH-host paths
- `cost_per_task.csv` named with no link or context
- "see X" / "details in Y" without a hyperlink

Required:
- A "📦 Download all raw data + scripts" link near the top of the article, pointing to a public bundle (tarball asset uploaded to blog or a GitHub release)
- Every CSV/figure/script reference inline-linked to either:
  - the bundle download
  - the GitHub source view, OR
  - a snippet in the article itself
- File names appear with one-line plain-language descriptions, e.g. `cost_per_task.csv (per-task NT$ cost summary, one row per (hardware, model, task) cell)`. Never naked filenames.

## R4 · Every figure must be click-to-enlarge (lightbox)

Readers need to be able to read axes/legends. Tiny inline figures lose half the information.

- All figures in the rendered article should open at full size on click — currently via parser-emitted `<figure><a target="_blank" href="..."><img ... /></a></figure>`.
- New figures: ship at ≥ 1600px wide PNG so the lightbox view is legible.

## R5 · "You can rerun this yourself" must be a real path, not a wave-of-hand

The article's reproducibility claim is one of the strongest reader hooks. It must be backed by:

- Public, downloadable raw data + scripts + prompts + env files (R3)
- Step-by-step rerun instructions in the bundle's `README.md`
- (Future) An interactive "rerun on this prompt, see if you get the same hash" mini-page linked from the article. Spec'd separately when prioritised.

If you cannot offer the reader a path to rerun, **don't claim reproducibility**.

## R6 · Sentence-by-sentence reader-question pass before publish

For academic / technical posts, do a final pass where you re-read every sentence and ask: **"if I were the reader, what question would I ask here?"** Then verify the article answers it within the next 1-2 paragraphs, or in a linked source.

Specifically check:
- Numbers: every "X×" or "NT$Y" must be traceable to a row in a referenced CSV / table.
- Claims: every "we measured X" must say which task, which hardware, which model, which run.
- Acronyms: SOAP / DDx / ICD-10 / MoE / PUE / e2e — define on first use.
- Comparisons: "5.5× slower" → slower than what? at what task? with what input length?
- Filenames / paths: cross-checked against R3.

If a sentence cannot survive a reader-question, rewrite it or delete it.

## R7 · Visualise hero / above-fold before celebrating

Hero card layout matters more than body. Use Chrome MCP to screenshot the top-of-page and grade against:

- Title length + line breaks (don't ship 60+ char titles wrapping 7 lines)
- Title vs excerpt redundancy (excerpt should add info, not paraphrase)
- Hero image crop (subjects must not be hidden by overlay text card)
- Mobile viewport (resize to 390px width, screenshot again)

If anything fails, fix before declaring the post live.

## R8 · Don't surface follow-up work as time estimates or "phase 2"

Per global memory `feedback_no_time_deferral.md`. Just execute the next step. Never write "預估 X 分鐘" / "Phase 2 timeline" / "next sprint."

## R9 · Bench reproducibility — the source of truth

Truth lives in:
- `raw_logs/{h200,mac}/*.jsonl` — one JSONL per (model, task) cell, one line per run
- `results/cost_per_task.csv` — derived; regenerate via `scripts/compute_cost_per_task.py`
- `results/raw_runs.csv`, `results/per_task_metrics.csv` — intermediate aggregations
- `figures/*.png` — generated via `scripts/plot_v2.py` from the CSVs above

**Never edit a CSV by hand.** If a number changes, change the JSONL or the cost-assumption dict + regenerate.

## R10 · Cost assumptions are a contract

`scripts/compute_cost_per_task.py` has a `COST_ASSUMPTIONS` dict (hardware price, amortisation years, active hours, power, electricity rate, PUE). The article's NT$ numbers are downstream of this dict.

- If a reader's clinic has different numbers, they edit the dict, rerun the script, get their own break-even. **Document this contract in the article**, not as a footnote — as a callout.
- Any change to the dict requires regenerating `cost_per_task.csv` + republishing all NT$ numbers in the article.

---

## Article publish workflow (current)

1. Edit `article/article.md` (template with `TBD: ...` placeholders)
2. `python scripts/render_article.py` → `article/article_filled.md`
3. (One-time per layout patch) verify Madgaa portal `parseArticleBlocks` supports every markdown construct used
4. `python scripts/publish_v2_draft.py article/article_filled.md --slug <slug> --status published` → bash script with SQL + asset uploads
5. Pipe through `ssh h200 sudo bash -s` to apply
6. **R1: open the live URL via Chrome MCP, audit top-to-bottom**
7. **R6: sentence-by-sentence reader-question pass**
8. Tell the user. Include the URL.

If R1 or R6 surfaces issues: fix in DB via `UPDATE blog_posts SET content_zh = $...$ WHERE slug = '...'`. Re-audit. Repeat until clean.
