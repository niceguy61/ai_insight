import { NextRequest, NextResponse } from "next/server";
import { sql, type SQL } from "drizzle-orm";
import { adminToken } from "../../../../lib/env";
import { getDb } from "../../../../db/queries";

export const dynamic = "force-dynamic";

/** 실행 이력 조회 — 소스·상태 필터 지원. */
export async function GET(req: NextRequest) {
  const token = req.headers.get("x-admin-token") ?? "";
  if (!adminToken() || token !== adminToken()) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }
  const sp = new URL(req.url).searchParams;
  const limit = Math.min(500, Math.max(1, Number(sp.get("limit") ?? "100") || 100));
  const source = sp.get("source");
  const status = sp.get("status");

  const db = getDb();
  try {
    const conds: SQL[] = [];
    if (source) conds.push(sql`source = ${source}`);
    if (status) conds.push(sql`status = ${status}`);
    const where = conds.length ? sql`WHERE ${sql.join(conds, sql` AND `)}` : sql``;

    const res = await db.execute(
      sql`SELECT id, source, kind, status, started_at, finished_at, stats, error
          FROM crawl_runs ${where}
          ORDER BY started_at DESC LIMIT ${limit}`,
    );
    return NextResponse.json({ ok: true, runs: res.rows });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e).slice(0, 200) }, { status: 503 });
  }
}
