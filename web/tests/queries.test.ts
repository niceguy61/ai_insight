import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import {
  getCrawlRuns,
  getConfig,
  getEntryBySlug,
  rankingEntries,
  searchEntries,
  setConfig,
  type Entry,
} from "../src/db/queries";

const TEST_DSN =
  process.env.DATABASE_URL_TEST ?? "postgresql://insight:insight@localhost:5434/insight_test";

const pool = new Pool({ connectionString: TEST_DSN });
const db = drizzle(pool);

const INSERT_ENTRY = `
  INSERT INTO entries (kind, slug, canonical_name, summary_ko, tags, category, repo_url,
                       stars, stars_delta_7d, installs, github_created_at, github_pushed_at)
  VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
  RETURNING id, slug`;

async function seed() {
  await pool.query(
    "TRUNCATE entries, appearances, metric_snapshots, crawl_runs, config CASCADE",
  );
  const now = new Date();
  const daysAgo = (d: number) => new Date(now.getTime() - d * 86_400_000);
  const rows = [
    // kind, slug, name, summary, tags, category, repo, stars, delta7, installs, created, pushed
    ["mcp", "a/stars", "A Stars", null, ["github"], "개발자 도구", "https://github.com/a/stars", 300, null, null, daysAgo(400), now],
    ["mcp", "b/trend", "B Trend", null, ["github"], "검색·브라우저", "https://github.com/b/trend", 200, 50, null, daysAgo(400), now],
    ["mcp", "c/null", "C Null", null, ["github"], "개발자 도구", "https://github.com/c/null", 100, null, null, daysAgo(400), now],
    ["skill", "d/installs", "D Installs", null, ["clawhub"], "생산성", "https://github.com/d/installs", 5, null, 900, daysAgo(400), now],
    ["mcp", "e/new", "E New", null, ["github"], "개발자 도구", "https://github.com/e/new", 10, 20, null, daysAgo(10), now],
    ["mcp", "f/notion", "Notion MCP", "노션 데이터베이스를 연결하는 MCP 서버", ["노션", "notion"], "생산성", "https://github.com/f/notion", 60, null, null, daysAgo(400), now],
  ];
  for (const r of rows) {
    const res = await pool.query(INSERT_ENTRY, r);
    if (r[1] === "f/notion") {
      await pool.query(
        `INSERT INTO appearances (entry_id, source, external_id, url, metrics)
         VALUES ($1,'github','f/notion','https://github.com/f/notion','{"stars":60}'),
                ($1,'skills_sh','f/notion/lark-doc','https://skills.sh/f/notion','{"installs":123}')`,
        [res.rows[0].id],
      );
      const sid = res.rows[0].id;
      for (const [day, stars] of [[13, 30], [7, 45], [0, 60]] as const) {
        await pool.query(
          `INSERT INTO metric_snapshots (entry_id, source, captured_at, metrics)
           VALUES ($1,'github',$2, $3)`,
          [sid, daysAgo(day), JSON.stringify({ stars })],
        );
      }
    }
  }
}

beforeAll(async () => {
  await seed();
});

afterAll(async () => {
  await pool.query("TRUNCATE entries, appearances, metric_snapshots, crawl_runs, config CASCADE");
  await pool.end();
});

describe("rankingEntries", () => {
  it("전체 스타 랭킹: stars desc", async () => {
    const items = await rankingEntries("stars", 10, db);
    expect(items.map((e) => e.slug).slice(0, 4)).toEqual(["a/stars", "b/trend", "c/null", "f/notion"]);
  });

  it("급상승: delta_7d 내림차순, NULL은 마지막", async () => {
    const items = await rankingEntries("trending", 10, db);
    expect(items.map((e) => e.slug).slice(0, 2)).toEqual(["b/trend", "e/new"]);
    expect(items.slice(2).every((e) => e.stars_delta_7d === null)).toBe(true);
    expect(items[2].slug).toBe("a/stars"); // NULL끼리는 stars desc
  });

  it("신규 급상승: 90일 이내 생성 + delta 순", async () => {
    const items = await rankingEntries("new", 10, db);
    expect(items.map((e) => e.slug)).toEqual(["e/new"]);
  });

  it("설치수 랭킹: installs desc", async () => {
    const items = await rankingEntries("installs", 10, db);
    expect(items[0].slug).toBe("d/installs");
    expect(items[0].installs).toBe(900);
  });

  it("종류 필터: kind가 지정되면 해당 종류만", async () => {
    const items = await rankingEntries("stars", 10, db, "skill");
    expect(items.map((e) => e.slug)).toEqual(["d/installs"]);
  });

  it("최신 탭: 생성일 최신순", async () => {
    const items = await rankingEntries("recent", 10, db);
    expect(items[0].slug).toBe("e/new"); // 10일 전 생성이 가장 최신
  });

  it("오프셋 페이징: 2페이지는 1페이지와 겹치지 않는다", async () => {
    const page1 = await rankingEntries("stars", 2, db);
    const page2 = await rankingEntries("stars", 2, db, undefined, undefined, 2);
    expect(page1.map((e) => e.slug)).toEqual(["a/stars", "b/trend"]);
    expect(page2.map((e) => e.slug)).toEqual(["c/null", "f/notion"]);
  });

  it("카테고리 필터도 랭킹에서 동작", async () => {
    const items = await rankingEntries("stars", 10, db, undefined, "생산성");
    expect(items.map((e) => e.slug)).toContain("f/notion");
    expect(items.map((e) => e.slug)).not.toContain("a/stars");
  });
});

describe("searchEntries", () => {
  it("한국어 검색: '노션'이 Notion MCP 엔트리를 찾는다", async () => {
    const { items, total } = await searchEntries({ q: "노션", limit: 10 }, db);
    expect(total).toBeGreaterThanOrEqual(1);
    expect(items.map((e) => e.slug)).toContain("f/notion");
  });

  it("카테고리 필터", async () => {
    const { items } = await searchEntries({ category: "개발자 도구", limit: 20 }, db);
    expect(items.every((e) => e.category === "개발자 도구")).toBe(true);
    expect(items.map((e) => e.slug)).toContain("a/stars");
    expect(items.map((e) => e.slug)).not.toContain("f/notion");
  });

  it("kind 필터", async () => {
    const { items } = await searchEntries({ kind: "skill", limit: 20 }, db);
    expect(items.length).toBeGreaterThanOrEqual(1);
    expect(items.every((e) => e.kind === "skill")).toBe(true);
  });
});

describe("getEntryBySlug", () => {
  it("appearances와 스냅샷 시계열을 포함한다", async () => {
    const detail = await getEntryBySlug("f/notion", db);
    expect(detail).not.toBeNull();
    expect(detail!.canonical_name).toBe("Notion MCP");
    expect(detail!.appearances.length).toBe(2);
    expect(detail!.star_history.length).toBe(3);
    expect(detail!.star_history[0].stars).toBe(30);
    expect(detail!.star_history[2].stars).toBe(60);
  });

  it("없는 slug는 null", async () => {
    expect(await getEntryBySlug("no/such", db)).toBeNull();
  });
});

describe("crawl runs / config", () => {
  it("getCrawlRuns와 getConfig/setConfig", async () => {
    await pool.query(
      "INSERT INTO crawl_runs (source, kind, status, stats) VALUES ('github','run','ok','{\"items\":1}')",
    );
    const runs = await getCrawlRuns(10, db);
    expect(runs.length).toBeGreaterThanOrEqual(1);
    expect(runs[0].source).toBe("github");

    await setConfig("llm", { base_url: "https://openrouter.ai/api/v1" }, db);
    const cfg = await getConfig("llm", db);
    expect(cfg).toEqual({ base_url: "https://openrouter.ai/api/v1" });
  });
});
