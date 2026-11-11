"""기존 raw_items의 TTL을 7일로 정리."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

from aic.config import load_config  # noqa: E402
from aic.db import connect  # noqa: E402


def main() -> None:
    conn = connect(load_config().database_url)
    cur = conn.execute(
        "UPDATE raw_items SET expires_at = fetched_at + interval '7 days'"
        " WHERE expires_at > fetched_at + interval '7 days'"
    )
    conn.commit()
    print("TTL 7일로 정리:", cur.rowcount, "행")


if __name__ == "__main__":
    main()
