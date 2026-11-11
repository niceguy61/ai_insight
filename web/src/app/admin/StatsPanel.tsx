"use client";

import { useCallback, useEffect, useState } from "react";

interface Stats {
  entries: number;
  eligible: number;
  summarized: number;
  shortDone: number;
  pending: number;
  llmCache: number;
  rawItems: number;
  snapshots: number;
  lastSync: { source: string; last_ok: string | null }[];
  errors: { source: string; started_at: string; error: string | null }[];
}

/** 백로그·캐시·소스별 sync 현황 패널 — /api/admin/stats. */
export default function StatsPanel({ token }: { token: string }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    fetch("/api/admin/stats", { headers: { "X-Admin-Token": token } })
      .then((r) => r.json())
      .then((b) => {
        if (b.ok) { setStats(b.stats); setErr(null); }
        else setErr(b.error);
      })
      .catch(() => setErr("조회 실패"));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  if (err) return <p className="empty">상태 조회 실패: {err}</p>;
  if (!stats) return <p className="empty">통계 불러오는 중…</p>;

  const pct = stats.eligible > 0 ? Math.round((stats.summarized / stats.eligible) * 100) : 0;

  const cards = [
    { label: "엔트리", value: stats.entries.toLocaleString(), cls: "" },
    { label: "요약 대상", value: stats.eligible.toLocaleString(), cls: "" },
    { label: "요약 완료", value: `${stats.summarized.toLocaleString()} (${pct}%)`, cls: "rise" },
    { label: "요약 대기", value: stats.pending.toLocaleString(), cls: "warn" },
    { label: "스타 스냅샷", value: stats.snapshots.toLocaleString(), cls: "" },
    { label: "README 캐시", value: stats.rawItems.toLocaleString(), cls: "" },
    { label: "LLM 캐시", value: stats.llmCache.toLocaleString(), cls: "" },
  ];

  return (
    <div className="statgrid">
      {cards.map((s) => (
        <div className="statcard" key={s.label}>
          <div className="label">{s.label}</div>
          <div className={`value ${s.cls}`}>{s.value}</div>
        </div>
      ))}
    </div>
  );
}
