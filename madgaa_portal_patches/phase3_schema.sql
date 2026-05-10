-- Phase 3 schema: add series_slug + series_index to blog_posts
ALTER TABLE blog_posts
  ADD COLUMN IF NOT EXISTS series_slug TEXT,
  ADD COLUMN IF NOT EXISTS series_index INTEGER;

CREATE INDEX IF NOT EXISTS idx_blog_posts_series ON blog_posts (series_slug, series_index);

-- Backfill the 4 published parts of mac-vs-h200 series
UPDATE blog_posts SET series_slug = 'mac-vs-h200-2026-05', series_index = 1
  WHERE slug = 'medical-ai-9-models-mac-vs-h200-cp-value-blog-2026-05';
UPDATE blog_posts SET series_slug = 'mac-vs-h200-2026-05', series_index = 2
  WHERE slug = 'mac-vs-h200-2-cost-accounting';
UPDATE blog_posts SET series_slug = 'mac-vs-h200-2026-05', series_index = 3
  WHERE slug = 'mac-vs-h200-3-full-table';
UPDATE blog_posts SET series_slug = 'mac-vs-h200-2026-05', series_index = 4
  WHERE slug = 'mac-vs-h200-4-buyer-recommendations';

SELECT slug, series_slug, series_index, status FROM blog_posts
  WHERE series_slug IS NOT NULL ORDER BY series_index;
