"""entries / appearances / raw_items 저장 로직.

모든 함수는 호출자가 관리하는 트랜잭션 안에서 동작한다(커밋하지 않음).
"""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from psycopg import Connection

from aic.merge import entry_slug, normalize_repo_url
from aic.models import RawItem

_ENTRY_UPDATABLE = """
    UPDATE entries SET
        canonical_name = COALESCE(%(canonical_name)s, canonical_name),
        repo_url       = COALESCE(%(repo_url)s, repo_url),
        homepage_url   = COALESCE(%(homepage_url)s, homepage_url),
        license        = COALESCE(%(license)s, license),
        stars          = COALESCE(%(stars)s, stars),
        installs       = GREATEST(COALESCE(%(installs)s, installs), installs),
        npm_downloads_monthly = COALESCE(%(npm_downloads_monthly)s, npm_downloads_monthly),
        github_created_at = COALESCE(%(github_created_at)s, github_created_at),
        github_pushed_at  = COALESCE(%(github_pushed_at)s, github_pushed_at),
        last_crawled_at   = now()
    WHERE id = %(entry_id)s
"""


def _slug_for(item: RawItem, repo_url: str | None, slug_override: str | None) -> str:
    if slug_override:
        return slug_override.strip().lower()
    normalized = normalize_repo_url(repo_url)
    if normalized:
        parts = normalized.rsplit("/", 2)
        return entry_slug(parts[-2], parts[-1])
    ext = item.external_id.strip().lower()
    if "/" in ext:
        return ext
    return f"{item.source}/{ext}"


def _entry_id_by_repo_url(conn: Connection, normalized: str | None) -> uuid.UUID | None:
    if not normalized:
        return None
    row = conn.execute(
        "SELECT id FROM entries WHERE repo_url = %s LIMIT 1", (normalized,)
    ).fetchone()
    return row[0] if row else None


def upsert_entry(
    conn: Connection,
    item: RawItem,
    kind: str,
    *,
    repo_url: str | None = None,
    canonical_name: str | None = None,
    slug: str | None = None,
    homepage_url: str | None = None,
    license: str | None = None,
    stars: int | None = None,
    installs: int | None = None,
    npm_downloads_monthly: int | None = None,
    github_created_at: datetime | None = None,
    github_pushed_at: datetime | None = None,
    tags: list[str] | None = None,
    category: str | None = None,
) -> uuid.UUID:
    """엔트리를 찾아 갱신하거나 새로 만들고 appearance를 붙인 뒤 entry id를 반환.

    매칭 순서: slug → repo_url 정규형. 병합 판정은 aic.merge.normalize_repo_url 기준.
    stars는 소스 최신값을 그대로, installs는 기존과의 최댓값을 유지한다.
    """
    normalized = normalize_repo_url(repo_url)
    final_slug = _slug_for(item, repo_url, slug)
    name = canonical_name or item.payload.get("name") or item.external_id

    row = conn.execute("SELECT id FROM entries WHERE slug = %s", (final_slug,)).fetchone()
    entry_id = row[0] if row else None
    if entry_id is None:
        entry_id = _entry_id_by_repo_url(conn, normalized)

    if entry_id is None:
        entry_id = uuid.uuid4()
        conn.execute(
            """
            INSERT INTO entries (id, kind, slug, canonical_name, repo_url, homepage_url,
                                 license, stars, installs, npm_downloads_monthly,
                                 github_created_at, github_pushed_at, tags, category,
                                 last_crawled_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
            """,
            (
                entry_id, kind, final_slug, name, normalized, homepage_url,
                license, stars or 0, installs, npm_downloads_monthly,
                github_created_at, github_pushed_at, tags or [], category,
            ),
        )
    else:
        params = dict(
            canonical_name=canonical_name, repo_url=normalized, homepage_url=homepage_url,
            license=license, stars=stars, installs=installs,
            npm_downloads_monthly=npm_downloads_monthly,
            github_created_at=github_created_at, github_pushed_at=github_pushed_at,
            entry_id=entry_id,
        )
        conn.execute(_ENTRY_UPDATABLE, params)

    attach_appearance(conn, entry_id, item.source, item.external_id, url=repo_url)
    return entry_id


def attach_appearance(
    conn: Connection,
    entry_id: uuid.UUID,
    source: str,
    external_id: str,
    url: str | None = None,
    metrics: dict | None = None,
) -> None:
    """(source, external_id) 유니크 기준 upsert. url은 비어있을 때만 채움."""
    conn.execute(
        """
        INSERT INTO appearances (entry_id, source, external_id, url, metrics)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source, external_id) DO UPDATE SET
            entry_id = EXCLUDED.entry_id,
            url = COALESCE(EXCLUDED.url, appearances.url),
            metrics = CASE
                WHEN EXCLUDED.metrics <> '{}'::jsonb THEN EXCLUDED.metrics
                ELSE appearances.metrics END,
            last_seen_at = now()
        """,
        (entry_id, source, external_id, url, json.dumps(metrics or {})),
    )


def insert_metric_snapshot(
    conn: Connection,
    entry_id: uuid.UUID,
    source: str,
    metrics: dict,
    captured_at: datetime | None = None,
) -> None:
    """지표 스냅샷 1건 기록. captured_at 기본은 now."""
    conn.execute(
        "INSERT INTO metric_snapshots (entry_id, source, captured_at, metrics)"
        " VALUES (%s, %s, COALESCE(%s, now()), %s)",
        (entry_id, source, captured_at, json.dumps(metrics)),
    )


def insert_raw_item(conn: Connection, item: RawItem, ttl_days: int = 7) -> None:
    expires = datetime.now(timezone.utc) + timedelta(days=ttl_days)
    conn.execute(
        "INSERT INTO raw_items (source, external_id, payload, expires_at) VALUES (%s,%s,%s,%s)",
        (item.source, item.external_id, json.dumps(item.payload), expires),
    )


def readme_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
