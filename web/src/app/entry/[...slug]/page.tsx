import Link from "next/link";
import { notFound } from "next/navigation";
import InstallCommands from "../../../components/InstallCommands";
import StarChart from "../../../components/StarChart";
import { getEntryBySlug } from "../../../db/queries";
import { KIND_LABEL, avatarUrl } from "../../../components/EntryCard";

export const dynamic = "force-dynamic";

const SOURCE_LABEL: Record<string, string> = {
  github: "GitHub",
  skills_sh: "skills.sh",
  clawhub: "ClawHub",
  mcp_registry: "MCP Registry",
  npm: "npm",
  geeknews: "GeekNews",
  backfill: "내부 백필",
};

export async function generateMetadata({ params }: { params: Promise<{ slug: string[] }> }) {
  const { slug: segments } = await params;
  return { title: `${segments.map(decodeURIComponent).join("/")} — ai_insight` };
}

export default async function EntryPage({ params }: { params: Promise<{ slug: string[] }> }) {
  const { slug: segments } = await params;
  const decoded = segments.map((s) => decodeURIComponent(s)).join("/");

  let entry = null;
  try {
    entry = await getEntryBySlug(decoded);
  } catch {
    return <p className="empty">데이터베이스에 연결할 수 없습니다. docker compose up -d 후 새로고침하세요.</p>;
  }
  if (!entry) notFound();

  const stars = (entry.star_history.at(-1)?.stars ?? entry.stars) as number;
  const primary = entry.repo_url ?? entry.homepage_url ?? entry.appearances.find((a) => a.url)?.url ?? null;
  const primaryLabel = entry.repo_url
    ? `GitHub에서 보기 ↗`
    : primary
      ? "원문에서 보기 ↗"
      : null;

  return (
    <article className="detail">
      <h1>
        {avatarUrl(entry) ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="davatar" src={avatarUrl(entry)!} alt="" width={44} height={44} />
        ) : null}
        {entry.canonical_name}
      </h1>
      <div className="subline">
        <span className="mono">{KIND_LABEL[entry.kind] ?? entry.kind}</span>
        {entry.category ? <span>{entry.category}</span> : null}
        <span className="mono">★ {stars.toLocaleString()}</span>
        {entry.stars_delta_7d && entry.stars_delta_7d > 0 ? (
          <span className="rise">+{entry.stars_delta_7d.toLocaleString()}/7d</span>
        ) : null}
        {entry.installs ? <span className="mono">설치 {entry.installs.toLocaleString()}</span> : null}
        {entry.npm_downloads_monthly ? (
          <span className="mono">npm/월 {entry.npm_downloads_monthly.toLocaleString()}</span>
        ) : null}
        {entry.license ? <span>{entry.license}</span> : null}
        {repoPath(entry) ? <span>{repoPath(entry)}</span> : null}
      </div>

      <div className="cta">
        {primary && primaryLabel ? (
          <a className="btn primary" href={primary} target="_blank" rel="noreferrer">
            {primaryLabel}
          </a>
        ) : null}
        <Link className="btn" href="/">
          랭킹으로
        </Link>
      </div>

      <section className="section">
        <h2>한 줄 · 상세 요약</h2>
        {entry.summary_short_ko ? (
          <p className="shortline">{entry.summary_short_ko}</p>
        ) : null}
        {entry.summary_ko ? (
          <p className="prose" style={{ lineHeight: 1.7 }}>
            {entry.summary_ko}
          </p>
        ) : (
          <p className="wait-note">
            요약이 아직 생성되지 않았습니다 — 수집기의 &ldquo;LLM 요약&rdquo; 실행 후 채워집니다.
            그 전까지 아래 설치·원문 링크로 바로 사용할 수 있습니다.
          </p>
        )}
        {entry.usage_ko ? (
          <p className="prose" style={{ lineHeight: 1.7, marginTop: 12 }}>
            {entry.usage_ko}
          </p>
        ) : null}
      </section>

      <section className="section">
        <h2>설치</h2>
        <InstallCommands cmds={entry.install_commands} />
      </section>

      <section className="section">
        <h2>스타 추이</h2>
        <StarChart
          points={entry.star_history.map((h) => ({
            time: new Date(h.captured_at).toISOString().slice(0, 10),
            value: h.stars,
          }))}
        />
      </section>

      <section className="section">
        <h2>어디서 화제가 되었나 — 원문 출처</h2>
        <ul className="sources">
          {entry.appearances.map((a) => (
            <li key={`${a.source}-${a.external_id}`}>
              <a href={a.url ?? "#"} target="_blank" rel="noreferrer">
                {SOURCE_LABEL[a.source] ?? a.source}
              </a>
              <span className="ext">{a.external_id}</span>
              {a.metrics && Object.keys(a.metrics).length > 0 ? (
                <span className="ext">{Object.entries(a.metrics).map(([k, v]) => `${k} ${String(v)}`).join(" · ")}</span>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}

function repoPath(entry: { repo_url: string | null }): string | null {
  return entry.repo_url ? entry.repo_url.replace("https://github.com/", "") : null;
}
