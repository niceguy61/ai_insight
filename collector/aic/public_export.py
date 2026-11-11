"""공개 데이터(Pages용 JSON) 생성기.

로컬 DB → web/public/data/ 샤드:
  manifest.json                     버전·집계·아카이브 날짜
  rank/{tab}.json                   탭별 정렬 완료 슬림 행 (클라이언트 페이징)
  search/index.json                 검색 인덱스 (이름·한줄요약·태그·테마)
  entry/{owner}/{repo}.json         상세 전문 + 90일 스타 히스토리
  archive/{date}.json               날짜별 그날 스냅샷 랭킹

모든 값은 공개 정보만 포함한다 (raw_items·DB 경로 등 비공개 데이터 제외).
"""
import datetime as dt
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

from aic.config import load_config  # noqa: E402
from aic.db import connect  # noqa: E402

TABS = {
    "stars": "stars > 0 AND github_pushed_at > now() - interval '180 days'",
    "trending": "true",
    "new": "github_created_at > now() - interval '90 days'",
    "recent": "stars > 0",
    "installs": "true",
}
ORDER = {
    "stars": "stars DESC",
    "trending": "stars_delta_7d DESC NULLS LAST, stars DESC",
    "new": "stars_delta_7d DESC NULLS LAST, stars DESC",
    "recent": "github_created_at DESC NULLS LAST, stars DESC",
    "installs": "installs DESC NULLS LAST, stars DESC",
}
LIMITS = {"trending": 2000, "new": 2000, "recent": 2000, "installs": 2000, "stars": 5000}

SLIM_COLS = (
    "id, kind, slug, canonical_name, summary_short_ko, stars,"
    " stars_delta_24h, stars_delta_7d, installs, category, tags,"
    " repo_url, homepage_url, github_created_at"
)


def _rows(conn, sql) -> list[dict]:
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def slim(row: dict, spark: list[int], momentum: int) -> dict:
    return {
        "slug": row["slug"],
        "n": row["canonical_name"],
        "k": row["kind"],
        "sh": row["summary_short_ko"],
        "st": row["stars"],
        "d7": row["stars_delta_7d"],
        "d24": row["stars_delta_24h"],
        "in": row["installs"],
        "cat": row["category"],
        "tg": row["tags"] or [],
        "sp": spark,
        "mo": momentum if momentum >= 2 else None,
        "cr": row["github_created_at"].date().isoformat() if row["github_created_at"] else None,
    }


def build(out_dir: Path) -> dict:
    cfg = load_config()
    conn = connect(cfg.database_url)
    out = Path(out_dir)
    (out / "rank").mkdir(parents=True, exist_ok=True)
    (out / "entry").mkdir(parents=True, exist_ok=True)
    (out / "archive").mkdir(parents=True, exist_ok=True)

    now = dt.datetime.now(dt.timezone.utc)
    manifest = {"generatedAt": now.isoformat(timespec="seconds"), "tabs": {}, "archiveDates": []}

    # 1) 랭킹 탭 × 5 (전체 목록, 정렬 완료 — 클라이언트는 페이징만)
    for tab, where in TABS.items():
        rows = _rows(
            conn,
            f"SELECT {SLIM_COLS} FROM entries WHERE entry_status='active' AND {where}"
            f" ORDER BY {ORDER[tab]} LIMIT {LIMITS[tab]}",
        )
        ids = [r["id"] for r in rows]
        sparks, momenta = _spark_batch(conn, ids)
        slim_rows = [
            slim(r, sparks.get(r["id"], []), momenta.get(r["id"], 0)) for r in rows
        ]
        (out / "rank" / f"{tab}.json").write_text(
            json.dumps(slim_rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        manifest["tabs"][tab] = len(slim_rows)

    # 2) 검색 인덱스
    idx = _rows(
        conn,
        """
        SELECT slug, canonical_name AS name, summary_short_ko AS sh, summary_ko,
               tags, category, kind, stars
        FROM entries WHERE entry_status='active'
        """,
    )
    index = [
        {
            "slug": r["slug"],
            "n": r["name"],
            "sh": r["sh"] or (r["summary_ko"] or "")[:22] or None,
            "tg": r["tags"] or [],
            "cat": r["category"],
            "k": r["kind"],
            "st": r["stars"],
        }
        for r in idx
    ]
    (out / "search").mkdir(parents=True, exist_ok=True)
    (out / "search" / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    # 3) 상세 전문 (등장 출처 + 90일 히스토리)
    entries = _rows(conn, "SELECT id, slug, kind, canonical_name, summary_short_ko, summary_ko,"
                          " usage_ko, install_commands, tags, category, repo_url, homepage_url,"
                          " license, stars, stars_delta_24h, stars_delta_7d, installs,"
                          " npm_downloads_monthly, github_created_at, github_pushed_at"
                          " FROM entries WHERE entry_status='active'")
    apps = {}
    for a in _rows(conn, "SELECT entry_id, source, external_id, url, metrics, last_seen_at"
                         " FROM appearances ORDER BY last_seen_at DESC"):
        apps.setdefault(a["entry_id"], []).append(
            {"source": a["source"], "external_id": a["external_id"],
             "url": a["url"], "metrics": a["metrics"]}
        )
    for e in entries:
        hist = conn.execute(
            """
            SELECT DISTINCT ON (captured_at::date) captured_at::date AS day,
                   (metrics->>'stars')::int AS stars
            FROM metric_snapshots
            WHERE entry_id=%s AND metrics ? 'stars'
              AND captured_at >= now() - interval '90 days'
            ORDER BY captured_at::date, captured_at DESC
            """,
            (e["id"],),
        ).fetchall()
        detail = {
            "slug": e["slug"],
            "kind": e["kind"],
            "name": e["canonical_name"],
            "short": e["summary_short_ko"],
            "summary": e["summary_ko"],
            "usage": e["usage_ko"],
            "install": e["install_commands"],
            "tags": e["tags"] or [],
            "category": e["category"],
            "repo": e["repo_url"],
            "homepage": e["homepage_url"],
            "license": e["license"],
            "stars": e["stars"],
            "d24": e["stars_delta_24h"],
            "d7": e["stars_delta_7d"],
            "installs": e["installs"],
            "npmMonthly": e["npm_downloads_monthly"],
            "createdAt": e["github_created_at"].date().isoformat() if e["github_created_at"] else None,
            "pushedAt": e["github_pushed_at"].date().isoformat() if e["github_pushed_at"] else None,
            "appearances": apps.get(e["id"], []),
            "history": [{"d": str(h[0]), "v": h[1]} for h in hist],
        }
        path = out / "entry" / f"{e['slug']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(detail, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # 4) 아카이브 (스냅샷 존재 날짜 × 그날 랭킹 상위 100)
    dates = [str(r[0]) for r in conn.execute(
        "SELECT DISTINCT captured_at::date AS day FROM metric_snapshots"
        " WHERE metrics ? 'stars' ORDER BY day DESC LIMIT 60"
    ).fetchall()]
    manifest["archiveDates"] = dates
    for day in dates:
        rows = _rows(conn, f"""
            SELECT {SLIM_COLS} FROM entries e
            JOIN LATERAL (
                SELECT (s.metrics->>'stars')::bigint AS day_stars
                FROM metric_snapshots s
                WHERE s.entry_id = e.id AND s.metrics ? 'stars'
                  AND s.captured_at::date = DATE '{day}'
                ORDER BY s.captured_at DESC LIMIT 1
            ) snap ON true
            WHERE e.entry_status='active'
            ORDER BY snap.day_stars DESC LIMIT 100
        """)
        ids = [r["id"] for r in rows]
        sparks, momenta = _spark_batch(conn, ids)
        slim_rows = [slim(r, sparks.get(r["id"], []), momenta.get(r["id"], 0)) for r in rows]
        (out / "archive" / f"{day}.json").write_text(
            json.dumps(slim_rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )

    manifest["entries"] = len(entries)
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    # 5) 아카이브 프루닝 — 90일 지난 스냅샷 파일 삭제 (보존 정책)
    cutoff = (now - dt.timedelta(days=90)).strftime("%Y-%m-%d")
    for f in (out / "archive").glob("*.json"):
        if f.stem < cutoff:
            f.unlink()

    conn.close()
    return manifest


def _spark_batch(conn, ids: list[str]) -> tuple[dict[str, list[int]], dict[str, int]]:
    """엔트리별 최근 14일 스파크 시리즈 + 모멘텀(연속 상승 일수)."""
    if not ids:
        return {}, {}
    id_list = ",".join(f"'{i}'" for i in ids)
    rows = conn.execute(
        f"""
        SELECT DISTINCT ON (entry_id, captured_at::date)
               entry_id, captured_at::date AS day, (metrics->>'stars')::int AS stars
        FROM metric_snapshots
        WHERE entry_id IN ({id_list}) AND metrics ? 'stars'
          AND captured_at >= now() - interval '14 days'
        ORDER BY entry_id, captured_at::date, captured_at DESC
        """
    ).fetchall()
    series: dict[str, list[tuple[str, int]]] = {}
    for eid, day, stars in rows:
        series.setdefault(eid, []).append((str(day), stars))
    sparks: dict[str, list[int]] = {}
    momenta: dict[str, int] = {}
    for eid, pts in series.items():
        pts.sort()
        values = [v for _, v in pts]
        sparks[eid] = values
        m = 0
        for i in range(len(values) - 1, 0, -1):
            if values[i] > values[i - 1]:
                m += 1
            else:
                break
        momenta[eid] = m
    return sparks, momenta


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).parents[2] / "web" / "public" / "data"
    )
    m = build(Path(out_dir))
    print(f"generated: {m['entries']} entries, tabs={m['tabs']}, archive days={len(m['archiveDates'])}")
