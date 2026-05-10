"""Publish the v2 article to Madgaa blog as a DRAFT (status=pending_approval).

Uses the same direct-DB-insert path as v1 because we want to preserve
the article content verbatim (the LLM compose_draft would rewrite).

Output: bash script printed to stdout. Pipe through `ssh h200 bash -s`.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import secrets
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

CONTRIBUTOR_ID = "11111111-2222-3333-4444-madgaaengbench"
CONTRIBUTOR_DISPLAY = "Madgaa Engineering"
CONTRIBUTOR_EMAIL = "weian@nomadsustaintech.com"
PUBLISH_TOKEN = f"mgb_{secrets.token_urlsafe(32)}"
PUBLISH_TOKEN_HASH = hashlib.sha256(PUBLISH_TOKEN.encode()).hexdigest()

BLOG_STORAGE_ROOT_IN_CONTAINER = "/app/data/blog"

PLACEHOLDER_TO_FILE = {
    "FIG1_PLACEHOLDER": "01_e2e_per_task.png",
    "FIG2_PLACEHOLDER": "02_cost_per_task.png",
    "FIG3_PLACEHOLDER": "03_cost_vs_e2e_2d.png",
    "FIG4_PLACEHOLDER": "04_break_even_concurrency.png",
    "FIG5_PLACEHOLDER": "05_output_size_consistency.png",
    "FIG6_PLACEHOLDER": "06_leaderboard_per_task.png",
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("article", type=Path)
    p.add_argument("--slug", required=True)
    p.add_argument("--title-zh", default=(
        "一台 Mac mini 能不能取代一張 H200？"
        "我們在四個醫療任務上實測了 Qwen 3.6 與 MedGemma 27B"
    ))
    p.add_argument("--title-en", default=(
        "Can a Mac mini replace an H200 for clinical AI? "
        "Measured on four medical tasks with Qwen 3.6 and MedGemma 27B"
    ))
    p.add_argument("--excerpt-zh", default=(
        "同一份 SOAP 摘要，Mac mini-class 慢 5.5×、貴 0.5×；H200 快 5.5×、貴 1.94×。"
        "本文用 4 個醫療任務 × 3 個模型 × 2 個硬體實測 CP 值——"
        "結論：single-user 場景 Mac mini 完勝 H200，break-even 約在 2 個並行使用者。"
    ))
    p.add_argument("--excerpt-en", default=(
        "Same SOAP summary task: Mac mini-class is 5.5x slower but per-task cheaper "
        "than H200 NVL. Break-even ~2 concurrent users. Single-user clinical AI "
        "should ship on Apple Silicon, not data-centre GPUs."
    ))
    p.add_argument("--status", default="pending_approval",
                   choices=["pending_approval", "published"],
                   help="default = pending_approval (draft)")
    args = p.parse_args()

    figs_dir = ROOT / "figures"
    article = args.article.read_text(encoding="utf-8")

    submission_id = str(uuid.uuid4())
    post_id = str(uuid.uuid4())
    asset_records = []
    for placeholder, fname in PLACEHOLDER_TO_FILE.items():
        path = figs_dir / fname
        if not path.exists():
            print(f"# WARN missing figure: {path}", file=sys.stderr)
            continue
        aid = str(uuid.uuid4())
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        storage_path = f"{BLOG_STORAGE_ROOT_IN_CONTAINER}/posts/{post_id}/{aid}.png"
        asset_records.append({
            "id": aid, "filename": f"{aid}.png",
            "original": fname, "storage_path": storage_path,
            "size": path.stat().st_size, "b64": b64,
            "placeholder": placeholder,
        })
        article = article.replace(
            placeholder, f"/api/blog/assets/{aid}", 1,
        )

    published_at = datetime.now(timezone.utc).isoformat()

    lines = [
        "#!/bin/bash",
        "set -euo pipefail",
        "BACKEND=madgaa_manager_system-backend-1",
        "POSTGRES=madgaa_manager_system-postgres-1",
        "WORK=$(mktemp -d /tmp/madgaa-publish-v2-XXXX)",
        f"echo Working dir: $WORK",
        f"echo Post ID: {post_id}",
        f"echo Slug: {args.slug}",
        f"echo Status: {args.status}",
        f"sudo docker exec $BACKEND mkdir -p {BLOG_STORAGE_ROOT_IN_CONTAINER}/posts/{post_id}",
    ]
    for asset in asset_records:
        local = f"$WORK/{asset['filename']}"
        lines.append(f"echo decoding {asset['original']} ...")
        lines.append(f"cat > {local}.b64 <<'EOF_B64'")
        b64 = asset["b64"]
        wrapped = "\n".join(b64[i: i + 76] for i in range(0, len(b64), 76))
        lines.append(wrapped)
        lines.append("EOF_B64")
        lines.append(f"base64 -d {local}.b64 > {local}")
        lines.append(f"sudo docker cp {local} $BACKEND:{asset['storage_path']}")

    sql = [
        "BEGIN;",
        "INSERT INTO blog_contributors (id, display_name, email, token_hash, status, notes)",
        f"VALUES ('{CONTRIBUTOR_ID}', '{CONTRIBUTOR_DISPLAY}', '{CONTRIBUTOR_EMAIL}',",
        f"        '{PUBLISH_TOKEN_HASH}', 'active', 'team-account-direct-insert')",
        "ON CONFLICT (id) DO NOTHING;",
        "",
        "INSERT INTO blog_submissions",
        "(id, contributor_id, title, locale, summary, body_text, notes, ai_expand,",
        " status, material_manifest)",
        f"VALUES ('{submission_id}', '{CONTRIBUTOR_ID}',",
        "        $$" + args.title_zh + "$$,",
        "        'zh-TW',",
        "        $$" + args.excerpt_zh + "$$,",
        "        $body$" + article + "$body$,",
        "        'Direct DB insert (publish_v2_draft.py)', 0,",
        f"        '{ 'published' if args.status == 'published' else 'draft_ready'}',",
        "        $${\"source\":\"direct_insert\",\"assetCount\":" + str(len(asset_records)) + "}$$);",
        "",
        "INSERT INTO blog_posts",
        "(id, submission_id, slug, title_zh, title_en, excerpt_zh, excerpt_en,",
        " content_zh, content_en, status, ai_expanded, approved_by, published_at)",
        f"VALUES ('{post_id}', '{submission_id}', '{args.slug}',",
        "        $$" + args.title_zh + "$$,",
        "        $$" + args.title_en + "$$,",
        "        $$" + args.excerpt_zh + "$$,",
        "        $$" + args.excerpt_en + "$$,",
        "        $czh$" + article + "$czh$,",
        "        $cen$"
        "[Traditional Chinese article in contentZh] Same SOAP summary task: "
        "Mac mini-class M4 32GB is 5.5x slower but per-task 1.94x cheaper than "
        "H200 NVL with same Qwen 3.6 35B-A3B Q4 model. Break-even ~2 concurrent "
        "users. Single-user clinical AI workflows ship on Apple Silicon. Mac mini "
        "32GB cannot fit MedGemma 27B (working set 22GB + OS 11GB > 32GB). "
        "Full data in benchmark_project/v2/.$cen$,",
        f"        '{args.status}', 0,",
        "        '" + ("system" if args.status == "published" else "''") + "',",
        f"        " + (f"'{published_at}'" if args.status == "published" else "NULL")
        + ");",
        "",
    ]
    for asset in asset_records:
        sql.append("INSERT INTO blog_assets")
        sql.append("(id, submission_id, post_id, kind, filename, original_filename,")
        sql.append(" mime_type, size_bytes, storage_path, metadata)")
        sql.append(f"VALUES ('{asset['id']}', '{submission_id}', '{post_id}', 'image',")
        sql.append(f"        '{asset['filename']}', '{asset['original']}',")
        sql.append(f"        'image/png', {asset['size']},")
        sql.append(f"        '{asset['storage_path']}', '{{}}');")
    sql.append("COMMIT;")
    sql.append(f"SELECT id, slug, status, published_at FROM blog_posts WHERE id='{post_id}';")

    lines.append("echo applying SQL ...")
    lines.append("sudo docker exec -i $POSTGRES psql -U madgaa -d madgaa <<'EOF_SQL'")
    lines.extend(sql)
    lines.append("EOF_SQL")
    lines.append("echo")
    lines.append(f"echo Post status: {args.status}")
    lines.append(f"echo Slug: {args.slug}")
    lines.append("echo Path on portal: /blog/p/" + args.slug)
    lines.append("echo Admin queue API: /api/blog/admin/queue")

    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
