"""지표 스냅샷 수집·급상승(delta) 재계산·콜드스타트 백필.

급상승의 정의: 최신 스냅샷 대비 24h(36h 창)/7d(6~8d 창) 이전 스냅샷과의 차이.
이전 시점 스냅샷이 없으면 NULL(데이터 부족) — 0이 아니라 "판단 불가"로 둔다.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from psycopg import Connection

from aic.store import insert_metric_snapshot


def capture_snapshots(
    conn: Connection,
    rows: "list[tuple[UUID, str, dict]]",
    captured_at: datetime | None = None,
) -> None:
    """(entry_id, source, metrics) 목록을 metric_snapshots에 기록."""
    for entry_id, source, metrics in rows:
        insert_metric_snapshot(conn, entry_id, source, metrics, captured_at=captured_at)


def _prev_stars(
    snaps: list[tuple[datetime, int]],
    latest_at: datetime,
    lo: timedelta,
    hi: timedelta,
    now: datetime,
) -> int | None:
    """[now-hi, now-lo] 구간에서 latest 이전 스냅샷 중 가장 최근의 stars."""
    upper = now - lo
    lower = now - hi
    candidates = [stars for at, stars in snaps if lower <= at <= upper and at < latest_at]
    return candidates[-1] if candidates else None


def recompute_deltas(conn: Connection, now: datetime | None = None) -> int:
    """각 엔트리의 stars_delta_24h/7d를 스냅샷 기반으로 재계산. 변경된 행 수 반환."""
    now = now or datetime.now(timezone.utc)
    rows = conn.execute(
        """
        SELECT entry_id, captured_at, (metrics->>'stars')::bigint AS stars
        FROM metric_snapshots
        WHERE metrics ? 'stars'
        ORDER BY entry_id, captured_at
        """
    ).fetchall()

    by_entry: dict[UUID, list[tuple[datetime, int]]] = defaultdict(list)
    for entry_id, at, stars in rows:
        by_entry[entry_id].append((at, int(stars)))

    updated = 0
    for entry_id, snaps in by_entry.items():
        latest_at, latest_stars = snaps[-1]
        prev_24 = _prev_stars(snaps, latest_at, timedelta(hours=24), timedelta(hours=36), now)
        prev_7 = _prev_stars(snaps, latest_at, timedelta(days=6), timedelta(days=8), now)
        d24 = latest_stars - prev_24 if prev_24 is not None else None
        d7 = latest_stars - prev_7 if prev_7 is not None else None

        row = conn.execute(
            "SELECT stars_delta_24h, stars_delta_7d FROM entries WHERE id=%s", (entry_id,)
        ).fetchone()
        if row and (row[0], row[1]) != (d24, d7):
            conn.execute(
                "UPDATE entries SET stars_delta_24h=%s, stars_delta_7d=%s WHERE id=%s",
                (d24, d7, entry_id),
            )
            updated += 1
    return updated


def backfill_star_history(
    conn: Connection,
    gh,
    limit: int = 500,
    now: datetime | None = None,
) -> int:
    """stars 상위 limit개 엔트리의 starred_at 히스토리로 1일/7일 경계 스냅샷을 합성.

    경계 ±12h 내 스냅샷이 이미 있으면 합성을 스킵(재실행 안전).
    처리(스타 히스토리 조회 성공)한 엔트리 수를 반환.
    """
    now = now or datetime.now(timezone.utc)
    entries = conn.execute(
        """
        SELECT id, slug, stars FROM entries
        WHERE repo_url IS NOT NULL AND stars > 0
        ORDER BY stars DESC LIMIT %s
        """,
        (limit,),
    ).fetchall()

    processed = 0
    consecutive_empty = 0
    total = len(entries)
    for idx, (entry_id, slug, stars) in enumerate(entries, start=1):
        try:
            stamps = gh.fetch_star_history(slug)
        except Exception:
            stamps = []  # 개별 엔트리 실패는 전체를 죽이지 않는다
        if not stamps:
            consecutive_empty += 1
            if consecutive_empty >= 20:
                print(f"[backfill] {idx}/{total} — 연속 20건 빈 응답(rate limit 추정), 백필 조기 중단", flush=True)
                break
            continue
        consecutive_empty = 0
        processed += 1
        if idx % 10 == 0 or idx == total:
            print(f"[backfill] {idx}/{total} processed (유효 {processed})", flush=True)

        for days in (1, 7):
            boundary = now - timedelta(days=days)
            gained_after = sum(1 for s in stamps if s > boundary)
            exists = conn.execute(
                """
                SELECT 1 FROM metric_snapshots
                WHERE entry_id=%s AND captured_at BETWEEN %s AND %s
                LIMIT 1
                """,
                (entry_id, boundary - timedelta(hours=12), boundary + timedelta(hours=12)),
            ).fetchone()
            if not exists:
                insert_metric_snapshot(
                    conn, entry_id, "backfill",
                    {"stars": stars - gained_after},
                    captured_at=boundary,
                )

        insert_exists = conn.execute(
            """
            SELECT 1 FROM metric_snapshots
            WHERE entry_id=%s AND captured_at BETWEEN %s AND %s
            LIMIT 1
            """,
            (entry_id, now - timedelta(hours=12), now + timedelta(hours=12)),
        ).fetchone()
        if not insert_exists:
            insert_metric_snapshot(conn, entry_id, "github", {"stars": stars}, captured_at=now)
    return processed
