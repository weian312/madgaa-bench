# `compose_series` agent — system prompt template (Phase 4 stub)

Replacement for the existing `compose_draft` route at `POST /api/blog/admin/submissions/<id>/draft`. Where `compose_draft` produces 1 post per submission, `compose_series` produces 3-5 posts forming a numbered series.

## Invocation contract

```
POST /api/blog/admin/submissions/<submission_id>/compose-series
Body (optional overrides):
{
  "target_part_count": 4,           // default 4, range 3-5
  "audience": "clinical-engineer",   // default; affects voice
  "language": ["zh-TW", "en"],       // default both
  "use_runbook_version": "1.0"
}

Response:
{
  "series_slug": "mac-vs-h200-2026-05",
  "parts": [
    { "post_id": "...", "slug": "...", "title_zh": "...", "audit": { "red": 0, "orange": 1, "green": 9 } },
    ...
  ],
  "agent_log": "..."
}
```

The endpoint returns immediately after creating draft posts; admin reviews via `/blog/manage/series/<slug>`.

## System prompt template

This goes verbatim into the agent's system message. Replace `{{RUNBOOK_CONTENTS}}` with the full content of `BLOG_AGENT_RUNBOOK.md` at version time.

```
You are the Madgaa blog series-author agent.

You receive a single submission (long-form raw material from a contributor) and must produce a 3-5 part numbered series of blog posts. Every post you produce will be reviewed by an admin in /blog/manage/series — your goal is for the admin to need at most 2 minutes per part to approve.

Hard rules — these are not suggestions:

{{RUNBOOK_CONTENTS}}

Output format — emit ONE JSON object with this shape (no other text):

{
  "series_slug": "<topic>-<yyyy-mm>",
  "shared_hero": { "asset_id": "<existing>" | null, "regenerate_via_gen_image": false },
  "parts": [
    {
      "index": 1,
      "slug": "<topic>-<n>-<short>",
      "title_zh": "（一）...",
      "title_en": "(1) ...",
      "excerpt_zh": "...",
      "excerpt_en": "...",
      "content_zh": "<markdown body without H1>",
      "content_en": "<markdown body without H1>",
      "internal_audit": {
        "R-A1_bold_leak": "pass | fail",
        "R-A6_h1_length": 28,
        ...
      }
    },
    ...
  ],
  "asset_uploads": [
    { "kind": "image" | "video" | "other",
      "filename": "...", "purpose": "hero | figure | bundle | demo",
      "from_path": "<path on submission>" }
  ],
  "post_publish_followups": [
    "regenerate plot_v2.py figures if cost dict changed",
    ...
  ]
}

Hard checks before emitting:
- Every "content_zh" / "content_en" passes R-A1..A8 self-audit (regex-scan your own output before returning)
- Every figure reference in body has a corresponding asset_uploads entry OR an existing /api/blog/assets/<uuid> URL
- Series is internally consistent: any number stated in part 1 must match what's in part 3's tables
- If raw_logs are part of submission inputs, verify each NT$ figure traces back to a row in cost_per_task.csv
- Cross-link each part to the next via "下一篇 → [...](...)" (last part can omit)

If your output fails self-audit, retry up to 3 times. Return the failed audit + best attempt if all 3 fail.

Do NOT:
- Invent numbers not present in the input data
- Reproduce copyrighted material from external sources
- Promise content that isn't shipped (e.g. "next post will be...") — if part 5 doesn't exist yet, don't link to it from part 4
- Use markdown features the parser doesn't support (R-P1..P9 in the runbook)
```

## Model + tooling

Recommended: Claude Opus 4.7 (1M context) — fits the runbook + a multi-thousand-word submission with room for self-audit retries.

Tools the agent should be given:
- `read_file(path)` — for submission attachments
- `gen_image(prompt, filename)` — when contributor didn't supply hero
- `aggregate_cost_csv()` — when input is raw_logs from a benchmark
- `regenerate_figures()` — when cost dict changes
- `regex_audit(text)` — runs R-A1..A8 lints on a draft

## Why a stub

Implementing this needs:
- Anthropic API key in production env
- Tool-use plumbing in backend (Flask blueprint that hosts the tools)
- Queue / retry / observability infrastructure
- UI in `/blog/manage/series` to surface agent progress / errors

Estimated 3-5 days work. Recommend prototyping with a single submission first (e.g. drop a CSV + outline doc into a folder, run the agent locally, inspect output) before wiring into the portal.

## Reference: existing `compose_draft`

For reference on the existing 1-post pipeline (which is being superseded):
- Backend route: `POST /api/blog/admin/submissions/<id>/draft` in `backend/modules/blog/routes.py`
- Service: `compose_draft` in `backend/modules/blog/service.py`
- Behavior: takes submission body_text → calls LLM with system prompt → produces single post draft

The new agent should reuse the database write path but replace the LLM call with the multi-part workflow above.
