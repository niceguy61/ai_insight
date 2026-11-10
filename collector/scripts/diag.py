"""진단: crawl_runs 최근 기록 + 소스별 appearances + kind 분포."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

from aic.config import load_config  # noqa: E402
from aic.db import connect  # noqa: E402


def main() -> None:
    conn = connect(load_config().database_url)
    print("=== 최근 crawl_runs 12건 ===")
    for src, status, started, stats, err in conn.execute(
        "SELECT source, status, started_at, stats, error FROM crawl_runs"
        " ORDER BY started_at DESC LIMIT 12"
    ).fetchall():
        print(f"  {started:%m-%d %H:%M} {src:<12} {status:<7} {stats} {err or ''}")

    print("\n=== appearances 소스별 ===")
    for src, n in conn.execute(
        "SELECT source, count(*) FROM appearances GROUP BY source ORDER BY count(*) DESC"
    ).fetchall():
        print(f"  {src}: {n}")

    print("\n=== kind별 엔트리 ===")
    for k, n in conn.execute("SELECT kind, count(*) FROM entries GROUP BY kind").fetchall():
        print(f"  {k}: {n}")

    n = conn.execute("SELECT count(*) FROM entries WHERE summary_ko IS NOT NULL").fetchone()[0]
    print(f"\nsummary_ko 있음: {n}")


if __name__ == "__main__":
    main()
