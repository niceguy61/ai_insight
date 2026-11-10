"""enrich 트랜잭션 종료 대기 — 최대 wait_seconds 동안 20초 간격 확인."""
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

from aic.config import load_config  # noqa: E402
from aic.db import connect  # noqa: E402


def main() -> None:
    wait_seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 420
    conn = connect(load_config().database_url)
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        rows = conn.execute(
            "SELECT 1 FROM pg_stat_activity"
            " WHERE datname='insight' AND state <> 'idle' AND pid <> pg_backend_pid()"
        ).fetchall()
        if not rows:
            print("DONE — 트랜잭션 종료됨 (커밋 완료)")
            return
        print(f"waiting... ({int(deadline - time.time())}s 남음)", flush=True)
        time.sleep(20)
    print("TIMEOUT — 아직 실행 중")


if __name__ == "__main__":
    main()
