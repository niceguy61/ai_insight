import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx

from aic.models import RawItem
from aic.snapshots import backfill_star_history, capture_snapshots, recompute_deltas
from aic.sources.github_source import GithubSource
from aic.store import upsert_entry

NOW = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)


def _mk_entry(db, slug="owner/repo", stars=100):
    return upsert_entry(
        db, RawItem("github", slug, {}), kind="mcp",
        repo_url=f"https://github.com/{slug}", stars=stars,
    )


def _snap(db, entry_id, at, stars):
    db.execute(
        "INSERT INTO metric_snapshots (entry_id, source, captured_at, metrics)"
        " VALUES (%s, 'test', %s, %s)",
        (entry_id, at, json.dumps({"stars": stars})),
    )


def _get_deltas(db, entry_id):
    row = db.execute(
        "SELECT stars_delta_24h, stars_delta_7d FROM entries WHERE id=%s", (entry_id,)
    ).fetchone()
    return row


def test_recompute_deltas_from_seeded_snapshots(db):
    entry_id = _mk_entry(db)
    _snap(db, entry_id, NOW - timedelta(days=7), 90)
    _snap(db, entry_id, NOW - timedelta(hours=24), 100)
    _snap(db, entry_id, NOW, 130)

    updated = recompute_deltas(db, now=NOW)
    assert updated == 1
    assert _get_deltas(db, entry_id) == (30, 40)


def test_single_snapshot_entry_keeps_null_deltas(db):
    entry_id = _mk_entry(db, slug="solo/repo", stars=5)
    _snap(db, entry_id, NOW, 5)

    updated = recompute_deltas(db, now=NOW)
    assert updated == 0
    assert _get_deltas(db, entry_id) == (None, None)


def test_stale_prev_outside_window_is_ignored(db):
    # 24h 이전 스냅샷이 36h 창 밖(2일 전)에 있으면 delta_24h는 NULL
    entry_id = _mk_entry(db)
    _snap(db, entry_id, NOW - timedelta(days=2), 10)
    _snap(db, entry_id, NOW, 50)

    recompute_deltas(db, now=NOW)
    d24, _d7 = _get_deltas(db, entry_id)
    assert d24 is None


def test_backfill_creates_synthetic_snapshots_and_deltas(db):
    entry_id = _mk_entry(db, stars=100)

    star_times = [NOW - timedelta(hours=2)] * 3 + [NOW - timedelta(days=5)] * 10
    body = [{"starred_at": t.isoformat().replace("+00:00", "Z"),
             "user": {"login": f"u{i}"}} for i, t in enumerate(star_times)]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/owner/repo/stargazers"
        return httpx.Response(200, json=body)

    gh = GithubSource(httpx.Client(transport=httpx.MockTransport(handler)), queries=[])

    processed = backfill_star_history(db, gh, limit=10, now=NOW)
    assert processed == 1

    snaps = db.execute(
        "SELECT captured_at, metrics->>'stars' FROM metric_snapshots"
        " WHERE entry_id=%s ORDER BY captured_at", (entry_id,),
    ).fetchall()
    # 현재(100) + 합성 2개(t-1d=97, t-7d=87)
    assert len(snaps) == 3
    assert snaps[0][1] == "87"  # 7일 경계: 100 - (3+10)
    assert snaps[1][1] == "97"  # 1일 경계: 100 - 3
    assert snaps[2][1] == "100"

    assert recompute_deltas(db, now=NOW) == 1
    assert _get_deltas(db, entry_id) == (3, 13)


def test_backfill_skips_existing_synthetic_snapshots(db):
    entry_id = _mk_entry(db, stars=100)

    star_times = [NOW - timedelta(hours=24)] * 3
    body = [{"starred_at": t.isoformat().replace("+00:00", "Z"),
             "user": {"login": "u"}} for t in star_times]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    gh = GithubSource(httpx.Client(transport=httpx.MockTransport(handler)), queries=[])
    backfill_star_history(db, gh, limit=10, now=NOW)
    count1 = db.execute(
        "SELECT count(*) FROM metric_snapshots WHERE entry_id=%s", (entry_id,)
    ).fetchone()[0]
    backfill_star_history(db, gh, limit=10, now=NOW)
    count2 = db.execute(
        "SELECT count(*) FROM metric_snapshots WHERE entry_id=%s", (entry_id,)
    ).fetchone()[0]
    # 두 번째 실행: 경계 ±12h 내 스냅샷이 이미 있어 합성 스킵 (현재 스냅샷만 중복 허용)
    assert count2 == count1
