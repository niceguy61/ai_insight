"use client";

import { useCallback, useEffect, useState } from "react";
import AdminTokenGate, { useAdminToken } from "../../../components/AdminTokenGate";

interface CrawlRun {
  id: string;
  source: string;
  kind: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  stats: Record<string, unknown> | null;
  error: string | null;
}

const SOURCES = ["github", "skills_sh", "clawhub", "mcp_registry", "npm",
  "snapshots", "enrich", "backfill", "rank_ref", "trending"];
const STATUSES = ["ok", "running", "error"];

function badge(status: string): string {
  if (status === "ok") return "badge ok";
  if (status === "error") return "badge error";
  if (status === "running") return "badge pending";
  return "badge";
}

export default function AdminLogsPage() {
  const { token, loaded } = useAdminToken();
  const [runs, setRuns] = useState<CrawlRun[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");

  const load = useCallback(async () => {
    setErr(null);
    try {
      const p = new URLSearchParams({ limit: "300" });
      if (source) p.set("source", source);
      if (status) p.set("status", status);
      const res = await fetch(`/api/admin/runs?${p}`, {
        headers: { "X-Admin-Token": token },
      });
      const body = await res.json();
      if (body.ok) setRuns(body.runs);
      else setErr(body.error ?? `HTTP ${res.status}`);
    } catch {
      setErr("조회 실패");
    }
  }, [token, source, status]);

  useEffect(() => {
    if (token) void load();
  }, [token, load]);

  return (
    <AdminTokenGate token={token} loaded={loaded}>
      <div>
        <h1 style={{ fontSize: 20, margin: "18px 0 8px" }}>실행 로그</h1>

        <div style={{ display: "flex", gap: 8, margin: "10px 0 4px", flexWrap: "wrap", alignItems: "center" }}>
          <select className="select" value={source} onChange={(e) => setSource(e.target.value)} aria-label="소스">
            <option value="">모든 소스</option>
            {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="상태">
            <option value="">모든 상태</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button type="button" className="pgbtn" onClick={load}>새로고침</button>
          <span className="count-note">{runs ? `${runs.length}건` : ""}</span>
        </div>

        {err ? (
          <p className="empty">조회 실패: {err}</p>
        ) : !runs ? (
          <p className="empty">불러오는 중…</p>
        ) : runs.length === 0 ? (
          <p className="empty">조건에 맞는 실행 이력이 없습니다.</p>
        ) : (
          <div className="ledger" style={{ marginTop: 12 }}>
            {runs.map((r) => (
              <div key={r.id} className="slip" style={{ gridTemplateColumns: "110px 90px minmax(0,1fr)" }}>
                <span className="rank" style={{ color: r.status === "error" ? "#ff6b6b" : undefined }}>
                  {r.source}
                </span>
                <span className="who">
                  <span className="titlerow">
                    <span className={badge(r.status)}>{r.status}</span>
                    <span className="name" style={{ fontWeight: 400, fontSize: 13 }}>
                      {r.finished_at
                        ? `${new Date(r.started_at).toLocaleTimeString("ko-KR")} → ${new Date(r.finished_at).toLocaleTimeString("ko-KR")}`
                        : `${new Date(r.started_at).toLocaleTimeString("ko-KR")} → 진행 중`}
                    </span>
                  </span>
                  <span className="brief" style={{ whiteSpace: "normal", lineHeight: 1.5 }}>
                    {r.error ? (
                      <span style={{ color: "#ff6b6b" }}>⚠ {r.error}</span>
                    ) : (
                      JSON.stringify(r.stats)
                    )}
                  </span>
                </span>
                <span className="nums">
                  <span className="installs">{new Date(r.started_at).toLocaleDateString("ko-KR")}</span>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </AdminTokenGate>
  );
}
