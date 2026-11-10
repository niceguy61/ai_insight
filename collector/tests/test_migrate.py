from conftest import MIGRATIONS_DIR, drop_all


def test_migrate_idempotent(test_db_conn):
    from aic.db import migrate

    drop_all(test_db_conn)
    applied1 = migrate(test_db_conn, MIGRATIONS_DIR)
    applied2 = migrate(test_db_conn, MIGRATIONS_DIR)
    assert "001_init.sql" in applied1
    assert applied2 == []
    rows = test_db_conn.execute(
        "select tablename from pg_tables where schemaname='public'"
    ).fetchall()
    names = {r[0] for r in rows}
    assert {
        "entries",
        "appearances",
        "metric_snapshots",
        "raw_items",
        "llm_cache",
        "crawl_runs",
        "config",
    } <= names
