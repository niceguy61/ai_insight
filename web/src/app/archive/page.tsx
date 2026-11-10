import Link from "next/link";
import EntryCard from "../../components/EntryCard";
import { archiveDates, archiveRanking, type Entry } from "../../db/queries";

export const dynamic = "force-dynamic";

export const metadata = { title: "아카이브 — ai_insight" };

export default async function ArchivePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const date = typeof sp.date === "string" && sp.date ? sp.date : undefined;

  let dates: string[] = [];
  let items: Entry[] | null = null;
  let error: string | null = null;
  try {
    dates = await archiveDates();
    if (date) items = await archiveRanking(date, 50);
  } catch {
    error = "데이터베이스에 연결할 수 없습니다.";
  }

  const selected = date && dates.includes(date) ? date : dates[0];

  return (
    <div>
      <h1 style={{ fontSize: 20, margin: "20px 0 6px" }}>아카이브</h1>
      <p className="summary" style={{ color: "#5c6066", fontSize: 13 }}>
        날짜별 스냅샷으로 그날의 랭킹을 그대로 봅니다. 스냅샷은 6시간마다 기록됩니다.
      </p>

      {error ? (
        <p className="empty">{error}</p>
      ) : (
        <>
          <nav className="cats" aria-label="스냅샷 날짜">
            {dates.map((d) => (
              <Link key={d} href={`/archive?date=${d}`} className={d === selected ? "on" : ""}>
                {d}
              </Link>
            ))}
          </nav>

          {items && items.length > 0 ? (
            <>
              <p className="count-note">{selected} 기준 · 그날 마지막 스냅샷 값</p>
              <div className="ledger">
                {items.map((e, i) => (
                  <EntryCard key={e.id} entry={e} rank={i + 1} />
                ))}
              </div>
            </>
          ) : selected ? (
            <p className="empty">그 날짜의 스냅샷이 아직 없습니다.</p>
          ) : (
            <p className="empty">스냅샷이 아직 없습니다 — 수집기가 6시간마다 기록합니다.</p>
          )}
        </>
      )}
    </div>
  );
}
