"""psycopg 연결 + 마이그레이션 러너."""
from pathlib import Path

import psycopg

MIGRATIONS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def connect(dsn: str) -> psycopg.Connection:
    """connect_timeout 10초 — Docker 포트 프록시 정체 시 무한 대기 대신 빠른 실패."""
    return psycopg.connect(dsn, connect_timeout=10)


def migrate(conn: psycopg.Connection, migrations_dir: Path) -> list[str]:
    """migrations_dir의 *.sql을 파일명 순서로 멱등 적용. 적용된 파일명 목록 반환."""
    conn.execute(MIGRATIONS_TABLE_DDL)
    conn.commit()

    applied = {r[0] for r in conn.execute("SELECT filename FROM schema_migrations").fetchall()}
    files = sorted(p.name for p in Path(migrations_dir).glob("*.sql"))

    newly: list[str] = []
    for name in files:
        if name in applied:
            continue
        sql = (Path(migrations_dir) / name).read_text(encoding="utf-8")
        with conn.transaction():
            conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (name,))
        newly.append(name)
    conn.commit()
    return newly
