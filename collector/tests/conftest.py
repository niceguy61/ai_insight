"""공용 fixture: 테스트용 PostgreSQL(DATABASE_URL_TEST) 준비.

테스트 DB가 없으면 자동 생성하고, 세션당 한 번 마이그레이션을 적용한다.
각 테스트는 `db` fixture를 써서 트랜잭션 롤백 격리를 얻는다.
"""
import os
import pathlib

import psycopg
import pytest

REPO_ROOT = pathlib.Path(__file__).parents[2]
MIGRATIONS_DIR = REPO_ROOT / "collector" / "db" / "migrations"

DEFAULT_TEST_DSN = "postgresql://insight:insight@localhost:5434/insight_test"


def test_dsn() -> str:
    """테스트 DB 접속 문자열(공개 헬퍼 — 라우트 테스트 등 별도 연결이 필요할 때)."""
    dsn = os.environ.get("DATABASE_URL_TEST")
    if dsn:
        return dsn
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DATABASE_URL_TEST="):
                return line.split("=", 1)[1].strip()
    return DEFAULT_TEST_DSN


_test_dsn = test_dsn  # 하위 호환 별칭


def _ensure_database(dsn: str) -> None:
    base, _, dbname = dsn.rpartition("/")
    admin = psycopg.connect(f"{base}/postgres", autocommit=True)
    try:
        exists = admin.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)
        ).fetchone()
        if not exists:
            admin.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        admin.close()


ALL_TABLES = [
    "appearances",
    "metric_snapshots",
    "raw_items",
    "llm_cache",
    "crawl_runs",
    "config",
    "entries",
    "schema_migrations",
]


def drop_all(conn: psycopg.Connection) -> None:
    """테스트 DB의 모든 테이블 제거(외래키 순서 고려). migrate 테스트 등에서 사용."""
    for table in ALL_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    conn.commit()


@pytest.fixture(scope="session")
def test_db_conn():
    dsn = _test_dsn()
    _ensure_database(dsn)
    conn = psycopg.connect(dsn)
    from aic.db import migrate

    migrate(conn, MIGRATIONS_DIR)
    yield conn
    conn.close()


@pytest.fixture
def db(test_db_conn):
    """테스트 종료 후 롤백으로 데이터 격리."""
    yield test_db_conn
    test_db_conn.rollback()
