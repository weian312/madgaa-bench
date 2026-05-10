"use client";

import { useEffect, useMemo, useState } from "react";

type Severity = "red" | "orange" | "green";
type LintResult = {
  id: string;
  label: string;
  severity: Severity;
  pass: boolean;
  detail?: string;
};

type Lint = {
  id: string;
  label: string;
  severity: Severity;
  run: () => { pass: boolean; detail?: string };
};

const article = (): string => {
  const root = document.querySelector("article, main, [data-blog-article]") || document.body;
  return (root as HTMLElement).innerText || "";
};

const LINTS: Lint[] = [
  {
    id: "R-A1",
    label: "Bold leak `**...`（parser 沒解析到 markdown bold）",
    severity: "red",
    run: () => {
      const txt = article();
      const m = txt.match(/\*\*[^\n*]{1,80}/g) || [];
      return { pass: m.length === 0, detail: m.slice(0, 3).join(" · ") };
    },
  },
  {
    id: "R-A2",
    label: "Quote `>` leak（多行 blockquote 第二行沒被剝掉）",
    severity: "red",
    run: () => {
      const txt = article();
      const m = txt.match(/(^|\n)>\s/g) || [];
      return { pass: m.length === 0, detail: `${m.length} occurrences` };
    },
  },
  {
    id: "R-A3",
    label: "HR leak `---`（hr 字面字串）",
    severity: "red",
    run: () => {
      const txt = article();
      const m = txt.match(/(^|\n)---+(\n|$)/g) || [];
      return { pass: m.length === 0 };
    },
  },
  {
    id: "R-A4",
    label: "Placeholder leak（PLACEHOLDER / TBD: / _TBD_）",
    severity: "red",
    run: () => {
      const txt = article();
      const m = txt.match(/PLACEHOLDER|TBD:|_TBD_/g) || [];
      return { pass: m.length === 0, detail: m.slice(0, 3).join(", ") };
    },
  },
  {
    id: "R-A5",
    label: "私有路徑 leak（h200:/data/... 等）",
    severity: "red",
    run: () => {
      const txt = article();
      const m = txt.match(/h200:\/|root@|sudo docker exec/g) || [];
      return { pass: m.length === 0, detail: m.slice(0, 3).join(", ") };
    },
  },
  {
    id: "R-A6",
    label: "H1 標題長度 ≤ 30 字（避免 hero 多行包覆）",
    severity: "orange",
    run: () => {
      const h1 = document.querySelector("h1");
      const t = h1?.textContent?.trim() || "";
      return {
        pass: t.length <= 30,
        detail: `${t.length} chars: "${t.slice(0, 50)}${t.length > 50 ? "…" : ""}"`,
      };
    },
  },
  {
    id: "R-A7",
    label: "Figure 都包 `<a>`（可點放大）",
    severity: "orange",
    run: () => {
      const figs = Array.from(document.querySelectorAll("figure"));
      const inline = figs.filter((f) => !!f.querySelector("img"));
      const clickable = inline.filter((f) => !!f.querySelector("a[href*='/api/blog/assets/']"));
      const heroOrCaption = inline.length - clickable.length <= 1; // hero may not be clickable
      return {
        pass: heroOrCaption,
        detail: `${clickable.length} clickable / ${inline.length} inline figures`,
      };
    },
  },
  {
    id: "R-A8",
    label: "提到 .csv / .py / .jsonl 必有 inline link",
    severity: "orange",
    run: () => {
      const txt = article();
      const filenames = txt.match(/[a-z_]+\.(csv|py|jsonl|sh)\b/gi) || [];
      const links = Array.from(document.querySelectorAll("a")).map((a) => a.href + " " + a.textContent);
      const orphan = filenames.filter((f) => !links.some((l) => l.includes(f)));
      const uniq = Array.from(new Set(orphan));
      return {
        pass: uniq.length === 0,
        detail: uniq.slice(0, 3).join(", "),
      };
    },
  },
  {
    id: "R-A9",
    label: "Bundle / repo 公開連結存在（github.com OR /api/blog/assets/）",
    severity: "green",
    run: () => {
      const links = Array.from(document.querySelectorAll("a"));
      const hasRepo = links.some((a) => /github\.com\//.test(a.href));
      const hasBundle = links.some((a) => /\/api\/blog\/assets\//.test(a.href));
      return {
        pass: hasRepo || hasBundle,
        detail: hasRepo ? "github linked" : hasBundle ? "blog asset linked" : "neither",
      };
    },
  },
  {
    id: "R-A10",
    label: "系列導覽連結（如系列文）",
    severity: "green",
    run: () => {
      const links = Array.from(document.querySelectorAll("a"));
      const prev = links.filter((a) => /上一篇|prev|←/.test(a.textContent || ""));
      const next = links.filter((a) => /下一篇|next|→/.test(a.textContent || ""));
      return {
        pass: prev.length > 0 || next.length > 0,
        detail: `prev: ${prev.length} · next: ${next.length}`,
      };
    },
  },
];

export default function BlogAuditPanel() {
  const [results, setResults] = useState<LintResult[]>([]);
  const [open, setOpen] = useState(true);

  const runLints = () => {
    const out: LintResult[] = LINTS.map((l) => {
      try {
        const r = l.run();
        return { id: l.id, label: l.label, severity: l.severity, pass: r.pass, detail: r.detail };
      } catch (e) {
        return { id: l.id, label: l.label, severity: l.severity, pass: false, detail: String(e) };
      }
    });
    setResults(out);
  };

  useEffect(() => {
    const t = setTimeout(runLints, 800);
    return () => clearTimeout(t);
  }, []);

  const summary = useMemo(() => {
    const reds = results.filter((r) => r.severity === "red" && !r.pass).length;
    const oranges = results.filter((r) => r.severity === "orange" && !r.pass).length;
    return { reds, oranges, total: results.length };
  }, [results]);

  const dot = (severity: Severity, pass: boolean) => {
    if (pass) return "bg-emerald-500";
    if (severity === "red") return "bg-rose-500";
    if (severity === "orange") return "bg-amber-500";
    return "bg-slate-400";
  };

  return (
    <div className="fixed right-4 bottom-4 z-50 max-w-md rounded-2xl border border-[#b58f4f]/45 bg-[#fff8eb] shadow-2xl shadow-[#11100e]/24 text-[#2b241b]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-semibold"
      >
        <span className="flex items-center gap-2">
          <span aria-hidden>🔍</span> Render Audit
          {summary.reds > 0 && (
            <span className="ml-1 inline-flex items-center justify-center rounded-full bg-rose-500/95 px-2 py-0.5 text-[11px] font-bold text-white">
              {summary.reds} red
            </span>
          )}
          {summary.oranges > 0 && (
            <span className="ml-1 inline-flex items-center justify-center rounded-full bg-amber-500/95 px-2 py-0.5 text-[11px] font-bold text-white">
              {summary.oranges} warn
            </span>
          )}
          {summary.reds === 0 && summary.oranges === 0 && results.length > 0 && (
            <span className="ml-1 inline-flex items-center justify-center rounded-full bg-emerald-500/95 px-2 py-0.5 text-[11px] font-bold text-white">
              all clean
            </span>
          )}
        </span>
        <span className="text-xs text-[#6f5f4b]">{open ? "▼" : "▲"}</span>
      </button>
      {open && (
        <div className="max-h-[60vh] overflow-y-auto border-t border-[#b58f4f]/22 px-4 py-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[12px] uppercase tracking-wider text-[#6f5f4b]">
              {results.length} lints · runbook R-A1..A10
            </span>
            <button
              type="button"
              onClick={runLints}
              className="rounded-full border border-[#b58f4f]/45 px-3 py-1 text-[11px] font-semibold text-[#6f5f4b] hover:bg-[#fff8eb]/85"
            >
              re-audit
            </button>
          </div>
          <ul className="space-y-2">
            {results.map((r) => (
              <li key={r.id} className="rounded-xl border border-[#b58f4f]/18 bg-white/70 px-3 py-2 text-[13px]">
                <div className="flex items-start gap-2">
                  <span className={`mt-1 inline-block h-2.5 w-2.5 rounded-full ${dot(r.severity, r.pass)}`} aria-hidden />
                  <div className="flex-1">
                    <div className="flex items-baseline gap-2">
                      <code className="text-[11px] text-[#6f5f4b]">{r.id}</code>
                      <span className={`text-[11px] uppercase tracking-wider ${
                        r.pass
                          ? "text-emerald-700"
                          : r.severity === "red"
                            ? "text-rose-600"
                            : "text-amber-600"
                      }`}>
                        {r.pass ? "ok" : r.severity === "red" ? "block" : "warn"}
                      </span>
                    </div>
                    <p className="font-medium leading-snug">{r.label}</p>
                    {r.detail && !r.pass && (
                      <p className="mt-1 break-words text-[12px] text-[#6f5f4b]">
                        {r.detail}
                      </p>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[11px] text-[#6f5f4b]">
            Refer to <a href="https://github.com/weian312/madgaa-bench/blob/main/BLOG_AGENT_RUNBOOK.md" target="_blank" rel="noopener noreferrer" className="underline">BLOG_AGENT_RUNBOOK.md</a> for full Rule definitions.
          </p>
        </div>
      )}
    </div>
  );
}
