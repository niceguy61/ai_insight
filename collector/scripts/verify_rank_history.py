"""rank_ref 주입 결과 검증: 상위 엔트리의 30일 히스토리 + 델타."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

from aic.config import load_config  # noqa: E402
from aic.db import connect  # noqa: E402

SQL = """
    SELECT e.canonical_name, e.slug, count(s.id) AS days,
           min(s.metrics->>'stars')::int AS min_stars,
           max(s.metrics->>'stars')::int AS max_stars,
           e.stars_delta_7d
    FROM entries e JOIN metric_snapshots s ON s.entry_id = e.id AND s.source = 'rank_ref'
    GROUP BY e.id, e.canonical_name, e.slug, e.stars_delta_7d
    ORDER BY max(s.metrics->>'stars')::int DESC LIMIT 8
"""


def main() -> None:
    conn = connect(load_config().database_url)
    print("=== rank_ref 히스토리 주입된 상위 엔트리 ===")
    for name, slug, days, mn, mx, d7 in conn.execute(SQL).fetchall():
        print(f"  {name[:26]:<26} {slug[:22]:<22} {days}일  {mn:,}→{mx:,}  7d델타={d7}")

    n = conn.execute("SELECT count(*) FROM rank_reference").fetchone()[0]
    print(f"\nrank_reference 총 행: {n}")


if __name__ == "__main__":
    main()
