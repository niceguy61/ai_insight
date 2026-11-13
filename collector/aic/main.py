"""수집기 엔트리포인트: migrate → 스케줄러 → control API(127.0.0.1:8111)."""
import logging
import socket
from pathlib import Path

import uvicorn

from aic.config import load_config
from aic.control_api import create_app
from aic.db import connect, migrate
from aic.scheduler import build_scheduler, start_enrich_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

MIGRATIONS_DIR = Path(__file__).parents[1] / "db" / "migrations"
HOST = "127.0.0.1"
PORT = 8111


def main() -> None:
    # 단일 인스턴스 가드 — 스케줄러 중복 기동(job 2배 발화)을 원천 차단
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((HOST, PORT))
    except OSError:
        logging.error("port %s already in use — another collector instance is running. Exiting.", PORT)
        return
    finally:
        probe.close()

    cfg = load_config()

    conn = connect(cfg.database_url)
    applied = migrate(conn, MIGRATIONS_DIR)
    conn.close()
    if applied:
        logging.info("migrations applied: %s", applied)

    conn_factory = lambda: connect(cfg.database_url)  # noqa: E731

    sched = build_scheduler(conn_factory)
    sched.start()
    start_enrich_worker(conn_factory)
    logging.info("scheduler started (github/snapshots 6h, skills 12h, registry/npm 24h) + enrich worker")

    app = create_app(conn_factory)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
