import { NextResponse } from "next/server";
import { adminToken } from "../../../../lib/env";
import { getDb } from "../../../../db/queries";
import { sql } from "drizzle-orm";

export const dynamic = "force-dynamic";

/** 요약 백로그·캐시·소스별 마지막 sync·최근 에러 — 어드민 상태 패널용. */
export async function GET(req: Request) {
  if (!adminToken() || req.headers.get("x-admin-token") !== adminToken()) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }
  const db = getDb();
  try {
    const one = async (q: ReturnType<typeof sql>) =>
      Number((await db.execute(q)).rows[0]?.n ?? 0);

    const total = await one(sql`SELECT count(*)::int AS n FROM entries WHERE entry_status='active'`);
    const eligible = await one(sql`
      SELECT count(*)::int AS n FROM entries
      WHERE entry_status='active' AND repo_url IS NOT NULL
        AND (COALESCE(stars,0) >= 50 OR COALESCE(installs,0) >= 100)`);
    const summarized = await one(sql`SELECT count(*)::int AS n FROM entries WHERE summary_ko IS NOT NULL`);
    const shortDone = await one(sql`SELECT count(*)::int AS n FROM entries WHERE summary_short_ko IS NOT NULL`);
    const pending = await one(sql`
      SELECT count(*)::int AS n FROM entries
      WHERE entry_status='active' AND repo_url IS NOT NULL
        AND (COALESCE(stars,0) >= 50 OR COALESCE(installs,0) >= 100)
        AND (summary_ko IS NULL OR summary_short_ko IS NULL OR readme_hash IS NULL)`);
    const llmCache = await one(sql`SELECT count(*)::int AS n FROM llm_cache`);
    const rawItems = await one(sql`SELECT count(*)::int AS n FROM raw_items`);
    const snapshots = await one(sql`SELECT count(*)::int AS n FROM metric_snapshots`);

    const syncs = (await db.execute(sql`
      SELECT source, max(finished_at)::text AS last_ok FROM crawl_runs
      WHERE status='ok' GROUP BY source ORDER BY source`)).rows;

    const errors = (await db.execute(sql`
      SELECT source, started_at::text AS started_at, error FROM crawl_runs
      WHERE status='error' ORDER BY started_at DESC LIMIT 5`)).rows;

    return NextResponse.json({
      ok: true,
      stats: {
        entries: total, eligible, summarized, shortDone, pending,
        llmCache, rawItems, snapshots,
        lastSync: syncs,
        errors,
      },
    });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e).slice(0, 200) }, { status: 500 });
  }
}
