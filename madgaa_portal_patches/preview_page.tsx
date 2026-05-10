import { notFound, redirect } from "next/navigation";
import { getLocale } from "next-intl/server";
import BlogArticleView from "@/components/blog/BlogArticleView";
import BlogAuditPanel from "@/components/blog/BlogAuditPanel";
import { backendJSON } from "@/lib/api";
import { getCurrentUser } from "@/lib/auth";
import { localeToBlogLanguage, requestedBlogLanguage } from "@/lib/blogLanguage";
import { canUseAgentConsole } from "@/lib/permissions";
import type { BlogQueuePayload } from "@/lib/blog";

type SearchParams = Promise<{ lang?: string | string[] }>;

export default async function BlogDraftPreviewPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams?: SearchParams }) {
  const user = await getCurrentUser();
  if (!user || !canUseAgentConsole(user.role)) redirect("/dashboard");

  const { id } = await params;
  const [queue, locale] = await Promise.all([
    backendJSON<BlogQueuePayload>("/api/blog/admin/queue"),
    getLocale(),
  ]);
  const query = searchParams ? await searchParams : {};
  const language = requestedBlogLanguage(query.lang) || localeToBlogLanguage(locale);
  const post = queue?.posts.find((item) => item.id === id);
  if (!post) notFound();

  const heroUrl = post.heroAssetId ? `/api/blog/admin/assets/${post.heroAssetId}` : post.heroUrl;

  return (
    <>
      <BlogArticleView
        post={post}
        backHref="/blog/manage"
        backLabel="← Blog 編輯台"
        heroUrl={heroUrl}
        eyebrow="Bilingual Article"
        assetScope="admin"
        initialLanguage={language}
      />
      <BlogAuditPanel />
    </>
  );
}
