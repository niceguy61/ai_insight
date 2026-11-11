"""GitHub 리포를 수동으로 카탈로그에 추가 (토픽 없는 리포 등 토픽 검색에 걸리지 않는 것).

사용: python scripts/add_repo.py owner/name [owner/name ...]
- GitHub API로 리포 메타데이터를 가져와 entries에 upsert
- raw_items(README는 enrich가 처리) + metric_snapshots(별) 기록
- 이미 있으면 갱신(멱등) — stars/설명/푸시시각 최신화
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx

from aic.config import load_config
from aic.db import connect
from aic.jobs import _github_kind, _parse_dt
from aic.models import RawItem
from aic.snapshots import capture_snapshots
from aic.store import insert_raw_item, upsert_entry


def fetch_repo(client: httpx.Client, full_name: str) -> dict | None:
    r = client.get(f"https://api.github.com/repos/{full_name}")
    if r.status_code != 200:
        print(f"  ✗ {full_name}: HTTP {r.status_code} — 건너뜀")
        return None
    return r.json()


def add_repo(conn, client: httpx.Client, full_name: str) -> bool:
    d = fetch_repo(client, full_name)
    if not d:
        return False

    from aic.sources.github_source import GithubSource

    item = RawItem(
        source="github",
        external_id=d["full_name"],
        payload={
            "name": d.get("name"),
            "description": d.get("description"),
            "topics": d.get("topics") or [],
            "stargazers_count": d.get("stargazers_count"),
            "homepage": d.get("homepage"),
            "license": {"spdx_id": (d.get("license") or {}).get("spdx_id")} if d.get("license") else None,
            "created_at": d.get("created_at"),
            "pushed_at": d.get("pushed_at"),
        },
    )
    kind = _github_kind(item.payload)
    entry_id = upsert_entry(
        conn, item, kind,
        repo_url=f"https://github.com/{item.external_id}",
        canonical_name=d.get("name") or item.external_id,
        homepage_url=d.get("homepage") or None,
        license=(d.get("license") or {}).get("spdx_id"),
        stars=d.get("stargazers_count"),
        github_created_at=_parse_dt(d.get("created_at")),
        github_pushed_at=_parse_dt(d.get("pushed_at")),
        tags=d.get("topics") or None,
    )
    insert_raw_item(conn, item)
    if d.get("stargazers_count") is not None:
        capture_snapshots(conn, [(entry_id, "github", {"stars": d["stargazers_count"]})])
    conn.commit()
    print(f"  ✓ {d['full_name']} — ⭐{d['stargazers_count']:,} kind={kind} (upsert 완료)")
    return True


def main() -> None:
    repos = [a.strip() for a in sys.argv[1:] if a.strip()]
    if not repos:
        print(__doc__)
        sys.exit(1)
    cfg = load_config()
    client = httpx.Client(timeout=30.0, headers={
        "Authorization": f"Bearer {cfg.github_token}",
        "Accept": "application/vnd.github+json",
    })
    conn = connect(cfg.database_url)
    ok = 0
    try:
        for repo in repos:
            if add_repo(conn, client, repo):
                ok += 1
    finally:
        conn.close()
        client.close()
    print(f"\n완료: {ok}/{len(repos)} 추가·갱신 — 요약은 다음 enrich 실행 때 자동 생성")


if __name__ == "__main__":
    main()
