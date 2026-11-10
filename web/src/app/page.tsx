import Link from "next/link";
import EntryCard from "../components/EntryCard";
import { rankingEntries, type Entry, type Ranking } from "../db/queries";
import { CATEGORIES, KINDS, RANK_TABS } from "../lib/taxonomy";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 50;

type SP = Record<string, string | string[] | undefined>;

function pick(sp: SP, key: string): string | undefined {
  const v = sp[key];
  return typeof v === "string" && v.trim() ? v.trim() : undefined;
}

function href(tab: string, kind?: string, category?: string, page?: number): string {
  const p = new URLSearchParams();
  if (tab && tab !== "stars") p.set("tab", tab);
  if (kind) p.set("kind", kind);
  if (category) p.set("category", category);
  if (page && page > 1) p.set("page", String(page));
  const qs = p.toString();
  return qs ? `/?${qs}` : "/";
}

export default async function Home({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const rawTab = pick(sp, "tab") ?? "stars";
  const tab: Ranking = (RANK_TABS.some((t) => t.key === rawTab) ? rawTab : "stars") as Ranking;
  const kind = pick(sp, "kind");
  const category = pick(sp, "category");
  const page = Math.max(1, Number(pick(sp, "page") ?? "1") || 1);
  const activeTab = RANK_TABS.find((t) => t.key === tab)!;

  let items: Entry[] = [];
  let error: string | null = null;
  try {
    items = await rankingEntries(tab, PAGE_SIZE, undefined, kind, category, (page - 1) * PAGE_SIZE);
  } catch {
    error = "데이터베이스에 연결할 수 없습니다. docker compose up -d 후 새로고침하세요.";
  }

  return (
    <div>
      <form className="searchline" action="/search">
        <input
          type="search"
          name="q"
          placeholder="이름·요약·태그로 검색 — 예: notion, 데이터베이스, 브라우저"
          aria-label="검색어"
        />
        <button type="submit">검색</button>
      </form>

      <nav className="ranktabs" aria-label="랭킹 기준">
        {RANK_TABS.map((t) => (
          <Link key={t.key} href={href(t.key, kind, category)} className={t.key === tab ? "on" : ""}>
            {t.label}
          </Link>
        ))}
      </nav>

      <nav className="kinds" aria-label="종류">
        <Link href={href(tab, undefined, category)} className={!kind ? "on" : ""}>
          전체
        </Link>
        {KINDS.map((k) => (
          <Link key={k.value} href={href(tab, k.value, category)} className={kind === k.value ? "on" : ""}>
            {k.label}
          </Link>
        ))}
      </nav>

      <nav className="cats" aria-label="카테고리">
        <Link href={href(tab, kind, undefined)} className={!category ? "on" : ""}>
          모든 테마
        </Link>
        {CATEGORIES.map((c) => (
          <Link key={c} href={href(tab, kind, c)} className={category === c ? "on" : ""}>
            {c}
          </Link>
        ))}
      </nav>

      <p className="count-note">
        {activeTab.desc}
        {kind ? ` · ${KINDS.find((k) => k.value === kind)?.label}` : ""}
        {category ? ` · ${category}` : ""}
        {items.length > 0 ? ` · ${PAGE_SIZE}개/페이지 · ${page}페이지` : ""}
      </p>

      {error ? (
        <p className="empty">{error}</p>
      ) : items.length === 0 ? (
        <p className="empty">
          이 조합의 데이터가 아직 없습니다 — 다른 테마·종류로 보거나, 수집이 더 진행되면 채워집니다.
        </p>
      ) : (
        <>
          <div className="ledger">
            {items.map((e, i) => (
              <EntryCard key={e.id} entry={e} rank={(page - 1) * PAGE_SIZE + i + 1} />
            ))}
          </div>
          <nav className="pager" aria-label="페이지">
            {page > 1 ? (
              <Link className="pgbtn" href={href(tab, kind, category, page - 1)}>
                ← 이전
              </Link>
            ) : (
              <span className="pgbtn off">← 이전</span>
            )}
            <span className="pgnum">{page}페이지</span>
            {items.length === PAGE_SIZE ? (
              <Link className="pgbtn" href={href(tab, kind, category, page + 1)}>
                다음 →
              </Link>
            ) : (
              <span className="pgbtn off">다음 →</span>
            )}
          </nav>
        </>
      )}
    </div>
  );
}
