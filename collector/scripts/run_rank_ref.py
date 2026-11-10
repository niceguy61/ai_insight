"""rank_ref job을 포그라운드에서 직접 실행 — 에러 추적용."""
import sys
import traceback
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

from aic.config import load_config  # noqa: E402
from aic.db import connect, migrate  # noqa: E402
from aic.jobs import _run_rank_ref  # noqa: E402


def main() -> None:
    cfg = load_config()
    conn = connect(cfg.database_url)
    migrate(conn, Path(__file__).parents[1] / "db" / "migrations")
    try:
        stats = _run_rank_ref(conn)
        print("OK:", stats)
    except Exception:
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
