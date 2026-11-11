"""현재 DB 실측: 테이블별 크기 + 행 수 + 예상 2배 시 크기."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

from aic.config import load_config  # noqa: E402
from aic.db import connect  # noqa: E402


def main() -> None:
    conn = connect(load_config().database_url)
    print("=== 테이블별 크기 (heap + index + toast) ===")
    rows = conn.execute("""
        SELECT relname,
               pg_total_relation_size(c.oid) AS total_bytes,
               c.reltuples::bigint AS approx_rows
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY pg_total_relation_size(c.oid) DESC
    """).fetchall()
    total = 0
    for name, b, rows_n in rows:
        total += b
        print(f"  {name:<20} {b/1024/1024:8.2f} MB  rows≈{max(rows_n, 0):,}")
    db_size = conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
    print(f"\nDB 전체: {db_size/1024/1024:.2f} MB (테이블 합 {total/1024/1024:.2f} MB)")
    print(f"2배 시: {db_size*2/1024/1024:.2f} MB ≈ {db_size*2/1024/1024/1024:.3f} GB")

    # 대략 행 수 (실측)
    for t in ("entries", "appearances", "metric_snapshots", "raw_items", "llm_cache", "crawl_runs"):
        n = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n:,} rows")


if __name__ == "__main__":
    main()
