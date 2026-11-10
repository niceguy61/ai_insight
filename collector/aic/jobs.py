"""소스 수집 job의 공통 흐름: fetch → store → 스냅샷 → crawl_runs 기록."""
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from aic.config import load_config
from aic.enrich.llm_client import get_settings
from aic.enrich.summarizer import run_enrichment
from aic.models import RawItem
from aic.snapshots import backfill_star_history, capture_snapshots, recompute_deltas
from aic.sources.clawhub import ClawhubSource
from aic.sources.github_ranking import fetch_ranking
from aic.sources.github_source import DEFAULT_QUERIES, GithubSource
from aic.sources.mcp_registry import McpRegistrySource
from aic.sources.npm_source import NpmSource
from aic.sources.skills_sh import SkillsShSource
from aic.store import attach_appearance, insert_raw_item, upsert_entry

HTTP_TIMEOUT = 30.0
TRACKED_LIMIT = 3000  # 스냅샷 tracked 상한 (설계 문서 §3)
BACKFILL_LIMIT = 500

VALID_SOURCES = {
    "github", "skills_sh", "clawhub", "mcp_registry",
    "npm", "snapshots", "enrich", "backfill", "rank_ref", "trending",
}


def _github(conn) -> GithubSource:
    cfg = load_config()
    client = httpx.Client(timeout=HTTP_TIMEOUT)
    return GithubSource(
        client,
        token=cfg.github_token or None,
        queries=list(DEFAULT_QUERIES),
    )


def _github_kind(payload: dict) -> str:
    topics = " ".join(payload.get("topics") or []).lower()
    name = (payload.get("name") or "").lower()
    text = f"{topics} {name}"
    if "skill" in text:
        return "skill"
    if "mcp" in text:
        return "mcp"
    return "library"


def _run_github(conn) -> dict:
    src = _github(conn)
    items = src.fetch()
    snapshot_rows = []
    for item in items:
        p = item.payload
        entry_id = upsert_entry(
            conn, item, _github_kind(p),
            repo_url=f"https://github.com/{item.external_id}",
            canonical_name=p.get("name") or item.external_id,
            homepage_url=p.get("homepage") or None,
            license=(p.get("license") or {}).get("spdx_id"),
            stars=p.get("stargazers_count"),
            github_created_at=_parse_dt(p.get("created_at")),
            github_pushed_at=_parse_dt(p.get("pushed_at")),
            tags=p.get("topics") or None,
        )
        insert_raw_item(conn, item)
        if p.get("stargazers_count") is not None:
            snapshot_rows.append((entry_id, "github", {"stars": p["stargazers_count"]}))
    capture_snapshots(conn, snapshot_rows)
    return {"items": len(items), "snapshots": len(snapshot_rows)}


def _run_skills_sh(conn) -> dict:
    src = SkillsShSource(httpx.Client(timeout=HTTP_TIMEOUT), mode="html")
    items = src.fetch()
    for item in items:
        upsert_entry(
            conn, item, "skill",
            repo_url=item.payload.get("repo_url"),
            canonical_name=item.payload.get("name") or item.external_id,
            installs=item.payload.get("installs"),
        )
        insert_raw_item(conn, item)
    return {"items": len(items)}


def _run_clawhub(conn) -> dict:
    src = ClawhubSource(httpx.Client(timeout=HTTP_TIMEOUT))
    items = src.fetch()
    for item in items:
        upsert_entry(
            conn, item, "skill",
            canonical_name=item.payload.get("displayName") or item.external_id,
            installs=item.payload.get("installs"),
        )
        insert_raw_item(conn, item)
    return {"items": len(items)}


def _run_mcp_registry(conn) -> dict:
    src = McpRegistrySource(httpx.Client(timeout=HTTP_TIMEOUT))
    items = src.fetch()
    for item in items:
        upsert_entry(
            conn, item, "mcp",
            repo_url=item.payload.get("repo_url"),
            canonical_name=item.payload.get("title") or item.external_id,
        )
        insert_raw_item(conn, item)
    return {"items": len(items)}


def _run_npm(conn) -> dict:
    src = NpmSource(httpx.Client(timeout=HTTP_TIMEOUT))
    items = src.fetch()
    for item in items:
        package = item.payload.get("package", {})
        monthly = (item.payload.get("downloads") or {}).get("monthly")
        entry_id = upsert_entry(
            conn, item, "mcp",
            repo_url=item.payload.get("repo_url"),
            canonical_name=package.get("name") or item.external_id,
            npm_downloads_monthly=monthly,
        )
        if item.payload.get("repo_url"):
            attach_appearance(conn, entry_id, "npm", item.external_id,
                              url=package.get("links", {}).get("npm"))
        insert_raw_item(conn, item)
    return {"items": len(items)}


def _run_snapshots(conn) -> dict:
    rows = conn.execute(
        """
        SELECT id, stars FROM entries
        WHERE repo_url IS NOT NULL AND stars > 0
        ORDER BY stars DESC LIMIT %s
        """,
        (TRACKED_LIMIT,),
    ).fetchall()
    capture_snapshots(conn, [(entry_id, "github", {"stars": stars}) for entry_id, stars in rows])
    updated = recompute_deltas(conn)
    return {"snapshots": len(rows), "deltas_updated": updated}


def _run_enrich(conn) -> dict:
    settings = get_settings(conn)
    if not settings.api_key:
        return {"skipped": "LLM_API_KEY 미설정 — 요약 스킵"}
    gh = _github(conn)
    stats = run_enrichment(
        conn, settings, limit=100,
        readme_fetcher=gh.fetch_readme,
        commit_each=True,  # 항목마다 커밋 — 웹에서 실시간 반영
    )
    return stats


def _run_backfill(conn) -> dict:
    gh = _github(conn)
    # 토큰 권한 사전 점검 — fine-grained PAT는 stargazers 접근이 막힐 수 있다
    probe = gh.fetch_star_history("n8n-io/n8n", max_pages=1)
    if not probe:
        return {
            "backfilled": 0,
            "skipped": "스타 히스토리 조회 실패 — GITHUB_TOKEN 권한 확인 "
                       "(classic 토큰 또는 fine-grained에 Public repositories read-only 필요)",
        }
    processed = backfill_star_history(conn, gh, limit=BACKFILL_LIMIT, commit_each=True)
    updated = recompute_deltas(conn)
    conn.commit()
    return {"backfilled": processed, "deltas_updated": updated}


# AI 타게팅 트렌딩 발굴 — github.com/trending(전 언어) 대신 AI 토픽 검색 기반
TRENDING_QUERIES = [
    "topic:ai-agents created:>2026-10-12",
    "topic:mcp-server created:>2026-10-12",
    "topic:claude-skills created:>2026-10-12",
    "topic:ai-coding created:>2026-10-12",
]


def _run_rank_ref(conn) -> dict:
    """EvanLi/Github-Ranking Top-100 전체 랭킹 스냅샷 → rank_reference (엔트리 아님, 참조 전용)."""
    from datetime import date

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        rows = fetch_ranking(client)
    if not rows:
        return {"items": 0, "skipped": "랭킹 파싱 실패"}
    today = date.today()
    for r in rows:
        conn.execute(
            """
            INSERT INTO rank_reference (snapshot_date, repo_full_name, rank, stars, language, description)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (snapshot_date, repo_full_name) DO UPDATE SET
                rank = EXCLUDED.rank, stars = EXCLUDED.stars, description = EXCLUDED.description
            """,
            (today, r["full_name"], r["rank"], r["stars"], r["language"], r["description"]),
        )
    return {"items": len(rows)}


def _run_trending(conn) -> dict:
    """AI 토픽 신생 발굴 — 최근 생성된 리포 중 별이 붙기 시작한 것."""
    client = httpx.Client(timeout=HTTP_TIMEOUT)
    gh = GithubSource(client, token=load_config().github_token or None,
                      queries=TRENDING_QUERIES, max_per_query=200)
    items = gh.fetch()
    new = 0
    for item in items:
        p = item.payload
        before = conn.execute("SELECT 1 FROM entries WHERE slug=%s", (item.external_id,)).fetchone()
        upsert_entry(
            conn, item, _github_kind(p),
            repo_url=f"https://github.com/{item.external_id}",
            canonical_name=p.get("name") or item.external_id,
            homepage_url=p.get("homepage") or None,
            license=(p.get("license") or {}).get("spdx_id"),
            stars=p.get("stargazers_count"),
            github_created_at=_parse_dt(p.get("created_at")),
            github_pushed_at=_parse_dt(p.get("pushed_at")),
            tags=p.get("topics") or None,
        )
        insert_raw_item(conn, item)
        if not before:
            new += 1
    return {"items": len(items), "new": new}


_JOBS = {
    "github": _run_github,
    "skills_sh": _run_skills_sh,
    "clawhub": _run_clawhub,
    "mcp_registry": _run_mcp_registry,
    "npm": _run_npm,
    "snapshots": _run_snapshots,
    "enrich": _run_enrich,
    "backfill": _run_backfill,
    "rank_ref": _run_rank_ref,
    "trending": _run_trending,
}


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def run_job(conn, source: str) -> dict:
    """crawl_runs 기록까지 포함한 job 실행. 실패 시 error 기록 후 재raise."""
    if source not in VALID_SOURCES:
        raise ValueError(f"unknown source: {source}")

    run_id = uuid4()
    conn.execute(
        "INSERT INTO crawl_runs (id, source, kind, status) VALUES (%s, %s, 'run', 'running')",
        (run_id, source),
    )
    try:
        stats = _JOBS[source](conn)
        conn.execute(
            "UPDATE crawl_runs SET status='ok', finished_at=now(), stats=%s WHERE id=%s",
            (json.dumps(stats, ensure_ascii=False), run_id),
        )
        return stats
    except Exception as exc:
        conn.execute(
            "UPDATE crawl_runs SET status='error', finished_at=now(), error=%s WHERE id=%s",
            (str(exc)[:2000], run_id),
        )
        raise


def delete_expired_raw_items(conn) -> int:
    cur = conn.execute("DELETE FROM raw_items WHERE expires_at < now()")
    return cur.rowcount or 0
