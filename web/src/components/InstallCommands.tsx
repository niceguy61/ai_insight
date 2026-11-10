"use client";

import { useState } from "react";

interface Cmd {
  target: string;
  cmd: string;
}

export default function InstallCommands({ cmds }: { cmds: Cmd[] | null }) {
  const [copied, setCopied] = useState<string | null>(null);

  if (!cmds || cmds.length === 0) {
    return <p className="summary">README에서 설치 명령을 찾지 못했습니다. 원문 링크에서 확인하세요.</p>;
  }

  async function copy(cmd: string) {
    try {
      await navigator.clipboard.writeText(cmd);
      setCopied(cmd);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // 클립보드 권한 없음 — 무시
    }
  }

  return (
    <div>
      {cmds.map((c, i) => (
        <div key={`${c.target}-${i}`} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
          <pre style={{ flex: 1, margin: 0 }}>
            <code>{c.cmd}</code>
          </pre>
          <span className="badge kind">{c.target}</span>
          <button type="button" onClick={() => copy(c.cmd)}>
            {copied === c.cmd ? "복사됨" : "복사"}
          </button>
        </div>
      ))}
    </div>
  );
}
