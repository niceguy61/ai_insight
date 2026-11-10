import Link from "next/link";
import EntryCard from "../components/EntryCard";
import { rankingEntries, type Entry, type Ranking } from "../db/queries";

export const dynamic = "force-dynamic";

const TABS: { key: Ranking; label: string; desc: string }[] = [
  { key: "stars", label: "전체 스타", desc: "원래 유명한 것 — 최근 180일 활성 기준" },
  { key: "trending", label: "스타 급상승", desc: "최근 7일 스타 증가분" },
  { key: "new", label: "신규 급상승", desc: "생성 90일 이내, 빠르게 오르는 프로젝트" },
  { key: "installs", label: "설치수", desc: "skills.sh·ClawHub·npm 기준" },
];

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const raw = typeof sp.tab === "string" ? sp.tab : "stars";
  const tab: Ranking = TABS.some((t) => t.key === raw) ? (raw as Ranking) : "stars";
  const active = TABS.find((t) => t.key === tab)!;

  let items: Entry[] = [];
  let error: string | null = null;
  try {
    items = await rankingEntries(tab, 50);
  } catch {
    error = "데이터베이스에 연결할 수 없습니다. docker compose up -d 후 다시 시도하세요.";
  }

  return (
    <div>
      <div className="searchbar">
        <form action="/search" style={{ display: "flex", gap: 8, flex: 1 }}>
          <input
            type="search"
            name="q"
            placeholder="MCP·스킬 검색 — 예: notion, 검색, 데이터베이스"
            aria-label="검색어"
          />
          <button type="submit">검색</button>
        </form>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <Link key={t.key} href={`/?tab=${t.key}`} className={t.key === tab ? "active" : ""}>
            {t.label}
          </Link>
        ))}
      </div>

      {error ? (
        <p className="empty">{error}</p>
      ) : items.length === 0 ? (
        <p className="empty">
          아직 데이터가 없습니다. 수집기(aic.main)를 실행하거나 /admin에서 &ldquo;지금 수집&rdquo;을 누르세요.
        </p>
      ) : (
        <>
          <p className="summary" style={{ color: "#8b949e", fontSize: 13 }}>
            {active.desc}
          </p>
          <div className="list">
            {items.map((e) => (
              <EntryCard key={e.id} entry={e} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
