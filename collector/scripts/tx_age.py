"""수집기의 열린 트랜잭션 나이 확인 — 진행 추정용."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

from aic.config import load_config  # noqa: E402
from aic.db import connect  # noqa: E402


def main() -> None:
    conn = connect(load_config().database_url)
    rows = conn.execute(
        "SELECT pid, application_name, state,"
        " date_trunc('second', now() - xact_start) AS tx_age,"
        " left(query, 50) AS q"
        " FROM pg_stat_activity"
        " WHERE datname='insight' AND state <> 'idle' AND pid <> pg_backend_pid()"
    ).fetchall()
    if not rows:
        print("열린 트랜잭션 없음 — 진행 중인 job이 없거나 이미 커밋됨")
    for pid, app, state, tx_age, q in rows:
        print(f"pid={pid} {state} tx_age={tx_age} | {q}")


if __name__ == "__main__":
    main()
