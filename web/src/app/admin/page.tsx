"use client";

import { useCallback, useEffect, useState } from "react";
import AdminTokenGate, { clearAdminToken, useAdminToken } from "../../components/AdminTokenGate";
import StatsPanel from "./StatsPanel";
import SyncTimes from "./SyncTimes";
import RunButtons from "./RunButtons";

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

function statusBadge(status: string): string {
  if (status === "ok") return "badge ok";
  if (status === "error") return "badge error";
  if (status === "running") return "badge pending";
  return "badge";
}

export default function AdminPage() {
  const { token, loaded, setToken } = useAdminToken();
  const [runs, setRuns] = useState<CrawlRun[] | null>(null);
  const [dbError, setDbError] = useState<string | null>(null);
  // 저장된 토큰이 서버에서 401로 거부된 상태 — 게이트에 "다시 입력" 탈출구를 띄우기 위한 플래그
  const [authFailed, setAuthFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/runs?limit=20", {
        headers: { "X-Admin-Token": token },
      });
      const body = await res.json();
      if (body.ok) {
        setRuns(body.runs);
        setDbError(null);
        setAuthFailed(false);
      } else {
        setDbError(body.error ?? `HTTP ${res.status}`);
        if (res.status === 401) setAuthFailed(true);
      }
    } catch {
      setDbError("runs 조회 실패");
    }
  }, [token]);

  useEffect(() => {
    if (token) void load();
  }, [token, load]);

  return (
    <AdminTokenGate
      token={token}
      loaded={loaded}
      failed={authFailed}
      onClearToken={() => {
        clearAdminToken();
        setToken("");
        setAuthFailed(false);
        setDbError(null);
      }}
    >
      <div className="container page">
        <h1 style={{ fontSize: 20, margin: "18px 0 8px" }}>수집 관리</h1>
        <StatsPanel token={token} />
        <RunButtons token={token} onDone={load} />
        <SyncTimes token={token} />
        <div style={{ marginTop: 10 }}>
          <a href="/admin/logs" style={{ fontSize: 13, color: "#6c8cff" }}>
            실행 로그 전체 보기
          </a>
        </div>

      </div>
    </AdminTokenGate>
  );
}