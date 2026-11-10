import Link from "next/link";
import type { Entry } from "../db/queries";
import { momentumDays } from "../db/queries";

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

export function avatarUrl(entry: Entry): string | null {
  if (!entry.repo_url?.includes("github.com/")) return null;
  const owner = entry.repo_url.replace("https://github.com/", "").split("/")[0];
  return owner ? `https://github.com/${owner}.png?size=48` : null;
}

function firstInstallCmd(entry: Entry): string | null {
  const cmds = entry.install_commands;
  if (cmds && cmds.length > 0 && cmds[0].cmd) return cmds[0].cmd;
  return null;
}

/** 72×26 미니 스파크라인 — 리스트에서 추이를 바로 본다. */
function MiniSpark({ series }: { series: { time: string; value: number }[] }) {
  if (series.length < 2) return <span className="spark" />;
  const values = series.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 72;
  const h = 26;
  const step = w / (series.length - 1);
  const rising = values[values.length - 1] >= values[0];
  const pts = series
    .map((p, i) => `${(i * step).toFixed(1)},${(h - 2 - ((p.value - min) / range) * (h - 4)).toFixed(1)}`)
    .join(" ");
  return (
    <svg className="spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <polyline
        points={pts}
        fill="none"
        stroke={rising ? "#0e9f6e" : "#c2beb2"}
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** 랭킹 장부의 한 행(전표). 한줄 요약(20자) → 설치 명령 → repo 경로 순으로 보여준다. */
export default function EntryCard({
  entry,
  rank,
  spark,
  momentum,
}: {
  entry: Entry;
  rank?: number;
  spark?: { time: string; value: number }[];
  momentum?: number;
}) {
  const short = entry.summary_short_ko?.trim() || entry.summary_ko?.trim();
  const cmd = firstInstallCmd(entry);
  const avatar = avatarUrl(entry);
  const repoPath = entry.repo_url?.replace("https://github.com/", "");

  return (
    <Link className="slip" href={`/entry/${entry.slug}`}>
      <span className={`rank${(rank ?? 99) <= 3 ? " top" : ""}`}>
        {rank !== undefined ? String(rank).padStart(2, "0") : ""}
      </span>
      <span className="who">
        <span className="titlerow">
          {avatar ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className="avatar" src={avatar} alt="" width={22} height={22} loading="lazy" />
          ) : null}
          <span className={`ktag ${entry.kind}`}>{KIND_LABEL[entry.kind] ?? entry.kind}</span>
          <span className="name">{entry.canonical_name}</span>
          {momentum && momentum >= 2 ? (
            <span className="momtag">🔥 {momentum}일 연속</span>
          ) : null}
        </span>
        {short ? (
          <span className="brief">{short}</span>
        ) : cmd ? (
          <span className="cmd">{cmd}</span>
        ) : repoPath ? (
          <span className="brief">{repoPath}</span>
        ) : null}
        {!short && !cmd ? (
          <span className="pending">요약·설치법 준비 중 — 상세에서 원문 링크로 확인</span>
        ) : null}
      </span>
      <span className="sparkcell">
        <MiniSpark series={spark ?? []} />
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
