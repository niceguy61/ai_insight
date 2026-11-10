import Link from "next/link";
import type { Entry } from "../db/queries";

export const KIND_LABEL: Record<string, string> = {
  mcp: "MCP",
  skill: "SKILL",
  plugin: "PLUGIN",
  library: "LIB",
};

export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function firstInstallCmd(entry: Entry): string | null {
  const cmds = entry.install_commands;
  if (cmds && cmds.length > 0 && cmds[0].cmd) return cmds[0].cmd;
  return null;
}

/** 랭킹 장부의 한 행(전표). 요약이 없으면 설치 명령을 앞세운다 — 이 포털의 산출물은 명령이니까. */
export default function EntryCard({ entry, rank }: { entry: Entry; rank?: number }) {
  const summary = entry.summary_ko?.trim();
  const cmd = firstInstallCmd(entry);
  const repoPath = entry.repo_url?.replace("https://github.com/", "");

  return (
    <Link className="slip" href={`/entry/${entry.slug}`}>
      <span className={`rank${(rank ?? 99) <= 3 ? " top" : ""}`}>
        {rank !== undefined ? String(rank).padStart(2, "0") : ""}
      </span>
      <span className="who">
        <span className="titlerow">
          <span className={`ktag ${entry.kind}`}>{KIND_LABEL[entry.kind] ?? entry.kind}</span>
          <span className="name">{entry.canonical_name}</span>
        </span>
        {summary ? (
          <span className="brief">{summary}</span>
        ) : cmd ? (
          <span className="cmd">{cmd}</span>
        ) : repoPath ? (
          <span className="brief">{repoPath}</span>
        ) : null}
        {!summary && !cmd ? (
          <span className="pending">요약·설치법 준비 중 — 상세에서 원문 링크로 확인</span>
        ) : null}
      </span>
      <span className="nums">
        <span className="stars">
          <span className="icon">⭐</span>
          {formatNumber(entry.stars)}
        </span>
        {entry.stars_delta_7d && entry.stars_delta_7d > 0 ? (
          <span className="delta">▲ {formatNumber(entry.stars_delta_7d)}<span className="unit">/7d</span></span>
        ) : entry.installs ? (
          <span className="installs">📥 {formatNumber(entry.installs)}</span>
        ) : null}
      </span>
    </Link>
  );
}
