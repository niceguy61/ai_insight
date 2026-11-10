import EntryCard from "../../components/EntryCard";
import { searchEntries, type Entry } from "../../db/queries";

export const dynamic = "force-dynamic";

const CATEGORIES = [
  "검색·브라우저",
  "파일·문서",
  "데이터베이스",
  "개발자 도구",
  "이미지·영상",
  "메모리·컨텍스트",
  "에이전트 프레임워크",
  "클라우드·인프라",
  "생산성",
  "기타",
];

const KINDS = [
  { value: "mcp", label: "MCP" },
  { value: "skill", label: "스킬" },
  { value: "plugin", label: "플러그인" },
  { value: "library", label: "라이브러리" },
];

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const pick = (k: string): string | undefined => {
    const v = sp[k];
    return typeof v === "string" && v.trim() ? v.trim() : undefined;
  };

  const params = {
    q: pick("q"),
    category: pick("category"),
    kind: pick("kind"),
    sort: pick("sort") as "stars" | "trending" | "relevance" | undefined,
    limit: 50,
  };

  let result: { items: Entry[]; total: number } | null = null;
  let error: string | null = null;
  try {
    result = await searchEntries(params);
  } catch {
    error = "데이터베이스에 연결할 수 없습니다. docker compose up -d 후 다시 시도하세요.";
  }

  return (
    <div>
      <form className="filterbar" style={{ display: "flex", gap: 8, margin: "16px 0", flexWrap: "wrap" }}>
        <input
          type="search"
          name="q"
          defaultValue={params.q}
          placeholder="검색어 (이름·요약·태그)"
          aria-label="검색어"
          style={{ flex: 1, minWidth: 200, background: "#161b22", border: "1px solid #21262d", color: "#e6edf3", borderRadius: 8, padding: "8px 12px" }}
        />
        <select name="category" defaultValue={params.category ?? ""} aria-label="카테고리">
          <option value="">모든 카테고리</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select name="kind" defaultValue={params.kind ?? ""} aria-label="종류">
          <option value="">모든 종류</option>
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
        <select name="sort" defaultValue={params.sort ?? "stars"} aria-label="정렬">
          <option value="stars">스타순</option>
          <option value="trending">급상승순</option>
          <option value="relevance">관련도순</option>
        </select>
        <button type="submit">필터 적용</button>
      </form>

      {error ? (
        <p className="empty">{error}</p>
      ) : result && result.total > 0 ? (
        <>
          <p style={{ color: "#8b949e", fontSize: 13 }}>총 {result.total}개</p>
          <div className="list">
            {result.items.map((e) => (
              <EntryCard key={e.id} entry={e} />
            ))}
          </div>
        </>
      ) : (
        <p className="empty">검색 결과가 없습니다.</p>
      )}
    </div>
  );
}
