import Link from "next/link";
import type { Entry } from "@/db/queries";

const KIND_LABEL: Record<string, string> = {
  mcp: "MCP",
  skill: "스킬",
  plugin: "플러그인",
  library: "라이브러리",
};

function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export default function EntryCard({ entry }: { entry: Entry }) {
  const summary = entry.summary_ko?.trim();
  return (
    <Link className="card" href={`/entry/${entry.slug}`}>
      <div className="title">{entry.canonical_name}</div>
      {summary ? (
        <p className="summary">{summary.length > 140 ? `${summary.slice(0, 140)}…` : summary}</p>
      ) : (
        <p className="summary">
          <span className="badge pending">요약 준비 중</span>
        </p>
      )}
      <div className="meta">
        <span className="badge kind">{KIND_LABEL[entry.kind] ?? entry.kind}</span>
        {entry.category ? <span className="badge">{entry.category}</span> : null}
        <span>⭐ {formatNumber(entry.stars)}</span>
        {entry.installs ? <span>📥 {formatNumber(entry.installs)}</span> : null}
        {entry.stars_delta_7d && entry.stars_delta_7d > 0 ? (
          <span className="badge up">▲7d {formatNumber(entry.stars_delta_7d)}</span>
        ) : null}
        {entry.stars_delta_24h && entry.stars_delta_24h > 0 ? (
          <span className="badge up">▲24h {formatNumber(entry.stars_delta_24h)}</span>
        ) : null}
        {entry.tags.slice(0, 4).map((t) => (
          <span key={t} className="badge">
            {t}
          </span>
        ))}
      </div>
    </Link>
  );
}
