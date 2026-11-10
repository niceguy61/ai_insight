import Link from "next/link";
import { notFound } from "next/navigation";
import InstallCommands from "../../../components/InstallCommands";
import Sparkline from "../../../components/Sparkline";
import { getEntryBySlug } from "../../../db/queries";

export const dynamic = "force-dynamic";

const SOURCE_LABEL: Record<string, string> = {
  github: "GitHub",
  skills_sh: "skills.sh",
  clawhub: "ClawHub",
  mcp_registry: "공식 MCP Registry",
  npm: "npm",
  geeknews: "GeekNews",
  backfill: "내부 백필",
};

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return { title: `${decodeURIComponent(slug)} — ai_insight` };
}

export default async function EntryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const decoded = decodeURIComponent(slug);

  let entry = null;
  try {
    entry = await getEntryBySlug(decoded);
  } catch {
    return <p className="empty">데이터베이스에 연결할 수 없습니다.</p>;
  }
  if (!entry) notFound();

  const stars = (entry.star_history.at(-1)?.stars ?? entry.stars) as number;

  return (
    <article className="detail">
      <h1>{entry.canonical_name}</h1>
      <div className="meta" style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 12, color: "#8b949e" }}>
        <span className="badge kind">{entry.kind.toUpperCase()}</span>
        {entry.category ? <span className="badge">{entry.category}</span> : null}
        <span>⭐ {stars.toLocaleString()}</span>
        {entry.stars_delta_7d ? <span className="badge up">▲7d {entry.stars_delta_7d}</span> : null}
        {entry.installs ? <span>📥 {entry.installs.toLocaleString()}</span> : null}
        {entry.npm_downloads_monthly ? <span>npm/월 {entry.npm_downloads_monthly.toLocaleString()}</span> : null}
        {entry.license ? <span className="badge">{entry.license}</span> : null}
      </div>

      <section className="section">
        <h2>요약</h2>
        {entry.summary_ko ? (
          <p style={{ lineHeight: 1.7 }}>{entry.summary_ko}</p>
        ) : (
          <p>
            <span className="badge pending">요약 준비 중</span>{" "}
            <span style={{ color: "#8b949e", fontSize: 13 }}>
              요약은 곧 생성됩니다 — 아래 원문 링크로 직접 확인할 수 있습니다.
            </span>
          </p>
        )}
      </section>

      {entry.usage_ko ? (
        <section className="section">
          <h2>사용법</h2>
          <p style={{ lineHeight: 1.7 }}>{entry.usage_ko}</p>
        </section>
      ) : null}

      <section className="section">
        <h2>설치</h2>
        <InstallCommands cmds={entry.install_commands} />
      </section>

      <section className="section">
        <h2>스타 추이 (최근 14일)</h2>
        <Sparkline points={entry.star_history.map((h) => h.stars)} />
      </section>

      <section className="section">
        <h2>원문 출처</h2>
        <ul style={{ lineHeight: 2, paddingLeft: 18 }}>
          {entry.repo_url ? (
            <li>
              <a href={entry.repo_url} target="_blank" rel="noreferrer" style={{ color: "#f97316" }}>
                GitHub — {entry.repo_url.replace("https://github.com/", "")}
              </a>
            </li>
          ) : null}
          {entry.homepage_url ? (
            <li>
              <a href={entry.homepage_url} target="_blank" rel="noreferrer" style={{ color: "#f97316" }}>
                홈페이지
              </a>
            </li>
          ) : null}
          {entry.appearances
            .filter((a) => a.url)
            .map((a) => (
              <li key={`${a.source}-${a.external_id}`}>
                <a href={a.url!} target="_blank" rel="noreferrer" style={{ color: "#f97316" }}>
                  {SOURCE_LABEL[a.source] ?? a.source}에서 보기
                </a>
                <span style={{ color: "#8b949e", fontSize: 12 }}> ({a.external_id})</span>
              </li>
            ))}
        </ul>
      </section>

      <p style={{ marginTop: 24 }}>
        <Link href="/" style={{ color: "#8b949e", fontSize: 13 }}>
          ← 랭킹으로
        </Link>
      </p>
    </article>
  );
}
