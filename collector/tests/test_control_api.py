import json

import httpx
import pytest
from fastapi.testclient import TestClient
from psycopg import connect

import aic.control_api as control_api
from aic.control_api import create_app, delete_expired_raw_items
from aic.models import RawItem
from aic.store import insert_raw_item
from conftest import test_dsn

TOKEN = "test-admin-token"


@pytest.fixture(autouse=True)
def _admin_token_env(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)


def _client() -> TestClient:
    app = create_app(conn_factory=lambda: connect(test_dsn()))
    return TestClient(app)


def test_run_requires_admin_token():
    c = _client()
    r = c.post("/run/github")
    assert r.status_code == 401
    r = c.post("/run/github", headers={"X-Admin-Token": "wrong"})
    assert r.status_code == 401


def test_run_with_token_and_monkeypatched_run_job(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_run_job(conn, source):
        calls.append(("run_job", source))
        return {"items": 3, "source": source}

    monkeypatch.setattr(control_api, "run_job", fake_run_job)
    c = _client()
    r = c.post("/run/github", headers={"X-Admin-Token": TOKEN})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["started"] is True  # 즉시 응답 — job은 백그라운드 스레드에서 실행

    # 백그라운드 스레드가 run_job을 실제로 호출했는지 대기 후 확인
    import time

    deadline = time.time() + 5
    while not calls and time.time() < deadline:
        time.sleep(0.05)
    assert ("run_job", "github") in calls


def test_run_unknown_source_returns_400():
    c = _client()
    r = c.post("/run/unknown-source", headers={"X-Admin-Token": TOKEN})
    assert r.status_code == 400


def test_run_enrich_returns_409_when_already_running():
    # enrich는 상시 워커와 수동 실행이 겹치면 429 폭주 — 락이 잡혀 있으면 409.
    # (이 가드에서 try_begin_enrich import 누락으로 500이 나온 적이 있었다 — 회귀 방지)
    from aic.jobs import try_begin_enrich

    assert try_begin_enrich() is True  # 락 선점
    try:
        c = _client()
        r = c.post("/run/enrich", headers={"X-Admin-Token": TOKEN})
        assert r.status_code == 409
        assert r.json()["ok"] is False
    finally:
        from aic.jobs import end_enrich

        end_enrich()


def test_run_enrich_starts_job_when_lock_free(monkeypatch):
    calls: list[str] = []

    def fake_run_job(conn, source):
        calls.append(source)
        return {"summarized": 1}

    monkeypatch.setattr(control_api, "run_job", fake_run_job)
    c = _client()
    r = c.post("/run/enrich", headers={"X-Admin-Token": TOKEN})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # 백그라운드 스레드가 run_job을 호출하고 락을 반납하는지 대기
    import time

    from aic.jobs import try_begin_enrich

    deadline = time.time() + 5
    while not calls and time.time() < deadline:
        time.sleep(0.05)
    assert calls == ["enrich"]
    # 락 반납 확인 — 스레드가 end_enrich()로 반납하면 획득에 성공한다
    import time as _t

    from aic.jobs import end_enrich

    deadline = _t.time() + 5
    acquired = False
    while _t.time() < deadline:
        if try_begin_enrich():
            acquired = True
            break
        _t.sleep(0.05)
    assert acquired
    end_enrich()


def test_status_lists_recent_crawl_runs():
    # 라우트는 별도 연결로 읽으므로 시드 데이터는 커밋되어 있어야 한다
    with connect(test_dsn()) as conn:
        conn.execute(
            "INSERT INTO crawl_runs (source, kind, status, stats) VALUES (%s,%s,%s,%s)",
            ("github", "run", "ok", json.dumps({"items": 3})),
        )
        conn.commit()

    c = _client()
    r = c.get("/status", headers={"X-Admin-Token": TOKEN})
    assert r.status_code == 200
    runs = r.json()["runs"]
    assert len(runs) >= 1
    assert runs[0]["source"] == "github"


def test_llm_models_proxies_list_models(monkeypatch):
    monkeypatch.setattr(
        control_api, "list_models",
        lambda s, client: ["model-a", "model-b"],
    )
    c = _client()
    r = c.get("/llm/models", headers={"X-Admin-Token": TOKEN})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "models": ["model-a", "model-b"]}


def test_delete_expired_raw_items(db):
    expired = RawItem("src", "old", {"x": 1})
    insert_raw_item(db, expired, ttl_days=30)
    db.execute("UPDATE raw_items SET expires_at = now() - interval '1 hour'"
               " WHERE external_id='old'")

    fresh = RawItem("src", "new", {"x": 2})
    insert_raw_item(db, fresh, ttl_days=30)

    deleted = delete_expired_raw_items(db)
    assert deleted >= 1
    remaining = {r[0] for r in db.execute("SELECT external_id FROM raw_items").fetchall()}
    assert "old" not in remaining
    assert "new" in remaining
