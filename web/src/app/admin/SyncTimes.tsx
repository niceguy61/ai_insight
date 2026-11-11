"use client";

import { useEffect, useState } from "react";

interface Stats {
  lastSync: { source: string; last_ok: string | null }[];
  errors: { source: string; started_at: string; error: string | null }[];
}

/** 소스별 마지막 성공 sync 시각 + 최근 에러 — /api/admin/stats. */
export default function SyncTimes({ token }: { token: string }) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    fetch("/api/admin/stats", { headers: { "X-Admin-Token": token } })
      .then((r) => r.json())
      .then((b) => { if (b.ok) setStats(b.stats); })
      .catch(() => {});
  }, [token]);

  if (!stats) return null;

  return (
    <div style={{ marginTop: 12, fontSize: 12, color: "#939cad" }}>
      {stats.lastSync.map((s) => (
        <div key={s.source}>
          <span style={{ color: "#6c8cff" }}>{s.source}</span>
          {" — "}
          {s.last_ok ? new Date(s.last_ok).toLocaleString("ko-KR") : "기록 없음"}
        </div>
      ))}
      {stats.errors.length > 0 ? (
        <div style={{ color: "#ff6b6b", marginTop: 6 }}>
          최근 에러: {stats.errors[0].source} — {stats.errors[0].error?.slice(0, 140)}
        </div>
      ) : null}
    </div>
  );
}
