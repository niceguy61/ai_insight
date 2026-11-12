"""공개 데이터(Pages용 JSON) 생성기.

로컬 DB → data/ 샤드:
  manifest.json                     버전·집계·아카이브 날짜
  rank/{tab}.json                   탭별 정렬 완료 슬림 행 (클라이언트 페이징)
  search/index.json                 검색 인덱스 (이름·한줄요약·태그·테마)
  metrics.json                      별수 지표 합본 {slug: [st, d7, d24, in, npm]} — 수집 때마다 바뀌는 유일한 큰 덩어리
  history.json                      스타 일별 추이 합본 {slug: [[YYYYMMDD, stars], ...]} — 차트용
  entry/{slug}.json                 상세 정적 전문 (요약·설치법·태그·출처 — 별수·히스토리 제외)
  archive/{date}.json               날짜별 그날 스냅샷 랭킹

별수(stars·delta·히스토리)를 entry 파일에서 분리한 이유: 수집 때마다 11k+ 파일이
변하면 git add/commit이 수 분씩 걸리고 repo가 폭발한다. 분리 후 배포 시 변경은
metrics·history·rank·search 등 한 자릿수 파일로 수렴한다.

모든 파일은 내용이 같으면 재작성하지 않는다(_write_if_changed — git 변경 최소화).
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
    "velocity": "stars_delta_7d IS NOT NULL AND stars_delta_7d > 0",
    "new": "github_created_at > now() - interval '90 days'",
    "recent": "stars > 0",
    "installs": "true",
}
ORDER = {
    "stars": "stars DESC",
    "trending": "stars_delta_7d DESC NULLS LAST, stars DESC",
    # 성장 속도 — 7일 전 대비 성장률: d7 / sqrt(7일 전 별수 + 1)
    # 0→1000 ≈ 1000점, 1000→10000 ≈ 285점, 100k→102k ≈ 6점 (급등 리포가 위로)
    "velocity": (
        "(stars_delta_7d::numeric / sqrt(GREATEST(stars - stars_delta_7d, 0) + 1)) DESC"
    ),
    "new": "stars_delta_7d DESC NULLS LAST, stars DESC",
    "recent": "github_created_at DESC NULLS LAST, stars DESC",
    "installs": "installs DESC NULLS LAST, stars DESC",
}
LIMITS = {"trending": 2000, "velocity": 2000, "new": 2000, "recent": 2000,
          "installs": 2000, "stars": 5000}

SLIM_COLS = (
    "id, kind, slug, canonical_name, summary_short_ko, stars,"
    " stars_delta_24h, stars_delta_7d, installs, category, tags,"
    " repo_url, homepage_url, github_created_at"
)


def _rows(conn, sql) -> list[dict]:
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _write_if_changed(path: Path, text: str) -> bool:
    """동일 내용이면 스킵 — 별수 갱신 때 git 변경 파일 수를 최소화. 썼으면 True."""
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == text:
                return False
        except OSError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def slim(row: dict, spark: list[int], momentum: int) -> dict:
    d7 = row["stars_delta_7d"] or 0
    base = max((row["stars"] or 0) - d7, 0)
    # 7일 전 대비 성장률(%) — 성장 속도 탭 표시용
    vl = round(100 * d7 / base, 1) if base > 0 else None
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
        "vl": vl,
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
        _write_if_changed(
            out / "rank" / f"{tab}.json",
            json.dumps(slim_rows, ensure_ascii=False, separators=(",", ":")),
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
    _write_if_changed(
        out / "search" / "index.json",
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
    )

    # 3) 별수 지표 합본 — 수집 때마다 바뀌는 유일한 큰 덩어리 (파일 1개)
    mrows = _rows(
        conn,
        "SELECT slug, stars, stars_delta_7d, stars_delta_24h, installs,"
        " npm_downloads_monthly FROM entries WHERE entry_status='active'",
    )
    metrics = {
        r["slug"]: [r["stars"], r["stars_delta_7d"], r["stars_delta_24h"],
                    r["installs"], r["npm_downloads_monthly"]]
        for r in mrows
    }
    _write_if_changed(
        out / "metrics.json",
        json.dumps(metrics, ensure_ascii=False, separators=(",", ":")),
    )

    # 4) 상세 전문 — 정적 내용만 (별수·히스토리는 metrics/history 합본으로).
    #    pushedAt 제외: 마지막 push 시각은 수집마다 바뀌어 정적 파일을 건드리는 주범.
    entries = _rows(conn, "SELECT id, slug, kind, canonical_name, summary_short_ko, summary_ko,"
                          " usage_ko, install_commands, tags, category, repo_url, homepage_url,"
                          " license, github_created_at"
                          " FROM entries WHERE entry_status='active'")
    apps = {}
    for a in _rows(conn, "SELECT entry_id, source, external_id, url, metrics, last_seen_at"
                         " FROM appearances ORDER BY last_seen_at DESC"):
        apps.setdefault(a["entry_id"], []).append(
            {"source": a["source"], "external_id": a["external_id"],
             "url": a["url"], "metrics": a["metrics"]}
        )
    for e in entries:
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
            "createdAt": e["github_created_at"].date().isoformat() if e["github_created_at"] else None,
            "appearances": apps.get(e["id"], []),
        }
        _write_if_changed(
            out / "entry" / f"{e['slug']}.json",
            json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
        )

    # 5) 스타 일별 추이 합본 (60일, 차트용) — 쿼리 1번으로 일괄 조회
    hist_rows = conn.execute(
        """
        SELECT entry_id, day, stars FROM (
            SELECT s.entry_id,
                   s.captured_at::date AS day,
                   (s.metrics->>'stars')::int AS stars,
                   ROW_NUMBER() OVER (
                       PARTITION BY s.entry_id, s.captured_at::date
                       ORDER BY s.captured_at DESC
                   ) AS rn
            FROM metric_snapshots s
            WHERE s.metrics ? 'stars' AND s.captured_at >= now() - interval '60 days'
        ) t
        WHERE rn = 1
        ORDER BY entry_id, day
        """
    ).fetchall()
    slug_by_id = {e["id"]: e["slug"] for e in entries}
    history: dict[str, list[list]] = {}
    for eid, day, stars in hist_rows:
        slug = slug_by_id.get(eid)
        if slug:
            history.setdefault(slug, []).append([int(day.strftime("%Y%m%d")), stars])
    _write_if_changed(
        out / "history.json",
        json.dumps(history, ensure_ascii=False, separators=(",", ":")),
    )

    # 6) 아카이브 (스냅샷 존재 날짜 × 그날 랭킹 상위 100)
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
        _write_if_changed(
            out / "archive" / f"{day}.json",
            json.dumps(slim_rows, ensure_ascii=False, separators=(",", ":")),
        )

    manifest["entries"] = len(entries)
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    # 7) 아카이브 프루닝 — 90일 지난 스냅샷 파일 삭제 (보존 정책)
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
