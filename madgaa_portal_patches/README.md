# Madgaa portal patches — Blog Agent Architecture (Phase 2 / 3 / 4 / 5)

These are deployment artifacts for the Madgaa Engineering portal blog system, captured here as a reference because the portal source is not in git on the production host.

Source of truth for "why these changes": [BLOG_AGENT_RUNBOOK.md](../BLOG_AGENT_RUNBOOK.md) — 26 雷 + 4 階段架構提案.

## Phase 2 — Admin Audit Panel ✅ Deployed 2026-05-10

### `BlogAuditPanel.tsx`
Drop into `intranet-portal/src/components/blog/BlogAuditPanel.tsx`.

Client-side React component (`"use client"`) that scans the rendered article DOM after mount and runs 10 lints (R-A1..A10). Displays a fixed-bottom-right traffic-light panel with red / orange / green dots per lint. Re-runnable via the "re-audit" button.

### `preview_page.tsx`
Drop into `intranet-portal/src/app/blog/preview/[id]/page.tsx` (replaces existing).

Adds `<BlogAuditPanel />` after `<BlogArticleView />` on the admin draft preview route. Visible only to users with `canUseAgentConsole` permission (admin / engineer / pm / bd).

### Build / deploy
```bash
cd /data/apps/Madgaa_manager_System
sudo docker compose build portal
sudo docker compose up -d portal
```

### Lint coverage (R-A1..A10)
| ID | Severity | What it catches |
|---|---|---|
| R-A1 | red | `**...` bold leak (parser missed it) |
| R-A2 | red | `\n> ` quote leak (multi-line blockquote) |
| R-A3 | red | `---` hr leak |
| R-A4 | red | `PLACEHOLDER` / `TBD:` / `_TBD_` leak |
| R-A5 | red | private path leak (`h200:/`, `root@`, `sudo docker exec`) |
| R-A6 | orange | H1 > 30 chars (hero will multi-line wrap) |
| R-A7 | orange | inline figures not wrapped in `<a>` (not click-to-enlarge) |
| R-A8 | orange | `.csv` / `.py` / `.jsonl` mentioned without inline link |
| R-A9 | green | bundle / repo public link present |
| R-A10 | green | series navigation links present (if applicable) |

## Phase 3 — Series schema + backfill ✅ Applied 2026-05-10

### `phase3_schema.sql`
Adds `series_slug TEXT` + `series_index INTEGER` columns to `blog_posts`, plus an index on (series_slug, series_index). Backfills the 4 published parts of the v2 series.

```sql
-- Apply via:
sudo docker exec -i madgaa_manager_system-postgres-1 psql -U madgaa -d madgaa < phase3_schema.sql
```

After apply, all 4 parts of `mac-vs-h200` series share `series_slug = 'mac-vs-h200-2026-05'` with indexes 1–4.

## Phase 3 UI / Phase 5 publish-all — Pending

Recommended next steps (requires admin login to test):

1. New backend routes:
   - `GET  /api/blog/admin/series/<series_slug>` → ordered list of parts with status + audit summary
   - `POST /api/blog/admin/series/<series_slug>/publish-all` → bulk set status='published' on all parts where audit is green
2. New frontend page:
   - `intranet-portal/src/app/(admin)/blog/manage/series/[seriesSlug]/page.tsx` — series management view with audit summary per part + publish-all button

Add `series_slug` + `series_index` to the queue API response (`/api/blog/admin/queue`) so the manage page can group posts by series.

## Phase 4 — `compose_series` agent (stub) — Pending

See [`compose_series_agent.md`](./compose_series_agent.md) for the system prompt template + invocation contract that the future agent will follow. Implementation TBD.

## Why these aren't in the portal repo

The Madgaa portal source on `h200:/data/apps/Madgaa_manager_System/` is not currently a git repo (verified 2026-05-10 — `git status` returns "fatal: not a git repository"). These patches were applied directly to the deployed source. Future maintenance should either:
- Init a git repo on the portal source path + commit, OR
- Move portal source into a git-tracked location and let CI deploy from there.
