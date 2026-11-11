"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import SyncTimes from "./SyncTimes";

const SOURCES: { key: string; label: string }[] = [
  { key: "github", label: "GitHub" },
  { key: "skills_sh", label: "skills.sh" },
  { key: "clawhub", label: "ClawHub" },
  { key: "mcp_registry", label: "MCP Registry" },
  { key: "npm", label: "npm" },
  { key: "snapshots", label: "스냅샷" },
  { key: "enrich", label: "LLM 요약" },
  { key: "rank_ref", label: "전체 랭킹" },
  { key: "trending", label: "AI 신규 발굴" },
];

export default function RunButtons({ token, onDone }: { token: string; onDone?: () => void }) {
  const router = useRouter();
  const [running, setRunning] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function run(source: string) {
    setRunning(source);
    setMessage(null);
    try {
      const res = await fetch("/api/admin/run", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Token": token },
        body: JSON.stringify({ source }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok && body.ok) {
        setMessage(`✅ ${source}: ${JSON.stringify(body.stats)}`);
        router.refresh();
        onDone?.();
      } else {
        setMessage(`❌ ${source}: ${body.error ?? `HTTP ${res.status}`}`);
      }
    } catch {
      setMessage(`❌ ${source}: 요청 실패`);
    } finally {
      setRunning(null);
    }
  }

  async function deploy() {
    setRunning("deploy");
    setMessage(null);
    try {
      const res = await fetch("/api/admin/deploy", {
        method: "POST",
        headers: { "X-Admin-Token": token },
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok && body.ok) {
        setMessage(`🚀 배포 완료 — GitHub Pages가 갱신 중입니다 (1-2분)\n${body.output ?? ""}`);
      } else {
        setMessage(`❌ 배포 실패: ${body.error ?? `HTTP ${res.status}`}`);
      }
    } catch {
      setMessage("❌ 배포 요청 실패");
    } finally {
      setRunning(null);
    }
  }

  return (
    <div>
      <div className="jobbtns">
        {SOURCES.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => run(s.key)}
            disabled={running !== null}
          >
            {running === s.key ? `${s.label} 실행 중…` : s.label}
          </button>
        ))}
      </div>
      <div className="jobbtns">
        <button type="button" onClick={deploy} disabled={running !== null}>
          {running === "deploy" ? "배포 중…" : "🚀 JSON 생성 & Pages push"}
        </button>
      </div>
      {message ? (
        <p style={{ marginTop: 12, fontSize: 13, color: "#939cad", whiteSpace: "pre-wrap" }}>
          {message}
        </p>
      ) : null}
    </div>
  );
}
