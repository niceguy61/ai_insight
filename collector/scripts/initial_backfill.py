"""초기 백필: 포털이 비어 있는 상태에서 첫 데이터를 채운다.

순서: github fetch → README 보강 → snapshots → star history backfill(500)
→ deltas 재계산 → LLM 요약(키 없으면 스킵) → skills_sh/clawhub/mcp_registry/npm.

실행: cd collector && .venv\\Scripts\\python scripts/initial_backfill.py
"""
import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))  # aic 임포트 가능

import httpx  # noqa: E402

from aic.config import load_config  # noqa: E402
from aic.db import connect, migrate  # noqa: E402
from aic.enrich.llm_client import get_settings  # noqa: E402
from aic.enrich.summarizer import run_enrichment  # noqa: E402
from aic.jobs import (  # noqa: E402
    _run_backfill,
    _run_clawhub,
    _run_github,
    _run_mcp_registry,
    _run_npm,
    _run_skills_sh,
    _run_snapshots,
)
from aic.snapshots import recompute_deltas  # noqa: E402

MIGRATIONS_DIR = Path(__file__).parents[1] / "db" / "migrations"


def main() -> None:
    cfg = load_config()
    conn = connect(cfg.database_url)
    applied = migrate(conn, MIGRATIONS_DIR)
    if applied:
        print(f"[migrate] applied: {applied}")

    gh = httpx.Client(timeout=60.0)

    steps = [
        ("github fetch (검색 + 저장 + 스냅샷)", lambda: _run_github(conn)),
        ("snapshots 캡처", lambda: _run_snapshots(conn)),
    ]
    print("\n=== star history backfill: GitHub가 stargazer 이력 API 철수로 스킵 ===")
    print("  (급상승은 스냅샷 축적으로 활성화 — 24h 델타는 내일부터)")
    for label, fn in steps:
        print(f"\n=== {label} ===")
        try:
            print(f"  -> {fn()}")
        except Exception as exc:
            print(f"  !! 실패(계속 진행): {exc}")

    print("\n=== deltas 재계산 ===")
    print(f"  -> updated {recompute_deltas(conn)}")
    conn.commit()

    print("\n=== LLM 요약 ===")
    settings = get_settings(conn)
    if not settings.api_key:
        print("  -> LLM_API_KEY 미설정 — 스킵 (.env에 키를 넣고 admin에서 'LLM 요약' 실행)")
    else:
        try:
            from aic.sources.github_source import DEFAULT_QUERIES, GithubSource

            src = GithubSource(gh, token=cfg.github_token or None, queries=list(DEFAULT_QUERIES))
            print(f"  -> {run_enrichment(conn, settings, limit=100, readme_fetcher=src.fetch_readme)}")
        except Exception as exc:
            print(f"  !! 실패(계속 진행): {exc}")

    for label, fn in [
        ("skills.sh", lambda: _run_skills_sh(conn)),
        ("clawhub", lambda: _run_clawhub(conn)),
        ("mcp_registry", lambda: _run_mcp_registry(conn)),
        ("npm", lambda: _run_npm(conn)),
    ]:
        print(f"\n=== {label} fetch ===")
        try:
            print(f"  -> {fn()}")
        except Exception as exc:
            print(f"  !! 실패(계속 진행): {exc}")

    conn.commit()
    total = conn.execute("SELECT count(*) FROM entries").fetchone()[0]
    print(f"\n[done] entries 총 {total}개 — 웹(http://localhost:3001)에서 확인하세요.")


if __name__ == "__main__":
    asyncio.run(asyncio.to_thread(main))
