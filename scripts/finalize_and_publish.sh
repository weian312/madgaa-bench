#!/usr/bin/env bash
# After all benches done, run: aggregate -> plot -> render article -> publish draft
set -uo pipefail
cd /Users/weian/Documents/benchmark_project/v2
PY=/Users/weian/Documents/benchmark_project/venv/bin/python3
RSYNC_OPTS="-az --partial"

echo "=== sync Mac raw_logs to h200 ==="
rsync $RSYNC_OPTS raw_logs/mac/ h200:/data/txtner-bench/madgaa-bench/v2/raw_logs/mac/
echo "=== pull h200 raw_logs ==="
rsync $RSYNC_OPTS h200:/data/txtner-bench/madgaa-bench/v2/raw_logs/h200/ raw_logs/h200/

echo "=== aggregate ==="
$PY scripts/compute_cost_per_task.py

echo "=== plot ==="
$PY scripts/plot_v2.py

echo "=== render article ==="
$PY scripts/render_article.py

echo "=== build publish bundle ==="
$PY scripts/publish_v2_draft.py article/article_filled.md \
  --slug medical-ai-mac-mini-vs-h200-cp-value-v3-2026-05 \
  --status pending_approval \
  > /tmp/publish_v3.sh

echo "=== delete old v2 draft ==="
ssh h200 'sudo docker exec madgaa_manager_system-postgres-1 psql -U madgaa -d madgaa -c "
DELETE FROM blog_assets WHERE post_id = (SELECT id FROM blog_posts WHERE slug=$$medical-ai-mac-mini-vs-h200-cp-value-2026-05$$);
DELETE FROM blog_posts WHERE slug = $$medical-ai-mac-mini-vs-h200-cp-value-2026-05$$;
DELETE FROM blog_submissions WHERE id NOT IN (SELECT submission_id FROM blog_posts);
"'

echo "=== apply v3 draft ==="
ssh h200 'bash -s' < /tmp/publish_v3.sh

echo "=== sync everything to h200 ==="
rsync $RSYNC_OPTS --exclude=venv --exclude=__pycache__ . h200:/data/txtner-bench/madgaa-bench/v2/
echo done
