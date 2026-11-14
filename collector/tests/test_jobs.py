"""소스 job 실행 공통 흐름(run_job) 테스트 — 직렬화·교착 재시도·배치 커밋.

2026-11-14: 수집기 재시작 시 모든 스케줄 job이 동시 발화해 clawhub×mcp_registry가
같은 entries 행을 다른 순서로 UPDATE하며 PostgreSQL 교착(DeadlockDetected)이
발생한 것의 회귀 방지.
"""
import threading
import time

import psycopg.errors

import aic.jobs as jobs
from aic.jobs import run_job
from aic.models import RawItem


def test_run_job_retries_on_deadlock(db, monkeypatch):
    calls: list[int] = []

    def flaky(conn):
        calls.append(1)
        if len(calls) < 2:
            raise psycopg.errors.DeadlockDetected()
        return {"items": 1}

    monkeypatch.setitem(jobs._JOBS, "clawhub", flaky)
    monkeypatch.setattr(jobs, "_RETRY_DELAYS", (0, 0))  # 테스트 속도 — 대기 없음

    stats = run_job(db, "clawhub")

    assert stats == {"items": 1}
    assert len(calls) == 2  # 교착 1회 → 롤백 후 재시도 성공


def test_run_job_gives_up_after_retries(db, monkeypatch):
    calls: list[int] = []

    def always_deadlock(conn):
        calls.append(1)
        raise psycopg.errors.DeadlockDetected(
            "deadlock detected: Process 1 waits for ShareLock; blocked by process 2")

    monkeypatch.setitem(jobs._JOBS, "mcp_registry", always_deadlock)
    monkeypatch.setattr(jobs, "_RETRY_DELAYS", (0, 0))

    try:
        run_job(db, "mcp_registry")
        raise AssertionError("교착이 재raise되어야 한다")
    except psycopg.errors.DeadlockDetected:
        pass
    assert len(calls) == 3  # 초기 시도 + 재시도 2회

    # crawl_runs에 error로 기록됐는지 — 마지막 실행 기준
    row = db.execute(
        "SELECT status, error FROM crawl_runs WHERE source='mcp_registry'"
        " ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    assert row[0] == "error"
    assert "deadlock" in row[1].lower()


def test_run_job_serializes_source_jobs(db, monkeypatch):
    started: list[str] = []

    def slow(conn):
        started.append("go")
        return {}

    monkeypatch.setitem(jobs._JOBS, "clawhub", slow)

    jobs._JOB_SERIAL.acquire()  # 다른 job이 DB 쓰는 중인 상태를 흉내
    try:
        t = threading.Thread(target=lambda: run_job(db, "clawhub"), daemon=True)
        t.start()
        time.sleep(0.5)
        assert started == []  # 락 잡혀 있는 동안 시작하지 않는다
    finally:
        jobs._JOB_SERIAL.release()
    t.join(timeout=5)
    assert started == ["go"]  # 락 반납 후 실행


def test_run_clawhub_batch_commits_and_plugin_kind(db, monkeypatch):
    rows = [
        RawItem("clawhub", "acme/alpha", {
            "displayName": "Alpha", "installs": 500,
        }),
        RawItem("clawhub", "acme/beta", {
            "displayName": "Beta", "installs": 100, "plugin": True,
        }),
    ]

    class FakeSource:
        source_name = "clawhub"

        def fetch(self):
            return rows

    monkeypatch.setattr(jobs, "ClawhubSource", lambda client: FakeSource())
    monkeypatch.setattr(jobs, "BATCH_SIZE", 2)  # 배치 커밋 경로를 지나게

    stats = jobs._run_clawhub(db)

    assert stats == {"items": 2, "skills": 1, "plugins": 1}
    kinds = {r[0] for r in db.execute(
        "SELECT kind FROM entries WHERE slug IN ('acme/alpha','acme/beta')"
    ).fetchall()}
    assert kinds == {"skill", "plugin"}
