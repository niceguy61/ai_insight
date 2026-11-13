"""수집기 control API — admin 전용(localhost 바인딩 + X-Admin-Token 게이트)."""
import logging
import threading

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import Client

from aic.config import load_config
from aic.enrich.llm_client import get_settings, list_models  # noqa: F401
from aic.jobs import VALID_SOURCES, delete_expired_raw_items, end_enrich, run_job  # noqa: F401

__all__ = ["create_app", "run_job", "delete_expired_raw_items"]

log = logging.getLogger(__name__)


def _run_in_background(conn_factory, source: str) -> None:
    """job을 별도 스레드에서 실행 — 이벤트 루프/HTTP 요청을 막지 않는다.

    진행 상황은 crawl_runs(/status)로 확인한다.
    """
    conn = conn_factory()
    try:
        stats = run_job(conn, source)
        conn.commit()
        log.info("background job %s finished: %s", source, stats)
    except Exception:
        conn.rollback()
        log.exception("background job %s failed", source)
    finally:
        if source == "enrich":
            end_enrich()
        conn.close()


def _authorized(request: Request) -> bool:
    expected = load_config().admin_token
    return request.headers.get("X-Admin-Token") == expected


def create_app(conn_factory) -> FastAPI:
    app = FastAPI(title="ai_insight collector", docs_url=None, redoc_url=None)

    @app.post("/run/{source}")
    async def run(source: str, request: Request):
        if not _authorized(request):
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        if source not in VALID_SOURCES:
            return JSONResponse(
                {"ok": False, "error": f"unknown source: {source}",
                 "valid": sorted(VALID_SOURCES)},
                status_code=400,
            )
        # 중복 실행 가드 — enrich는 상시 워커/수동 실행과 겹치면 429 폭주
        if source == "enrich":
            if not try_begin_enrich():
                return JSONResponse(
                    {"ok": False, "error": "enrich가 이미 실행 중입니다 (상시 워커) — 진행 상황은 실행 기록(/status)에서 확인"},
                    status_code=409,
                )
        # 즉시 응답 — job은 백그라운드 스레드에서 실행 (enrich는 수십 분 소요 가능)
        threading.Thread(
            target=_run_in_background, args=(conn_factory, source), daemon=True, name=f"job-{source}"
        ).start()
        return {"ok": True, "source": source, "started": True,
                "note": "진행 상황은 GET /status (crawl_runs)로 확인"}

    @app.get("/status")
    async def status(request: Request):
        if not _authorized(request):
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        conn = conn_factory()
        try:
            rows = conn.execute(
                """
                SELECT id, source, kind, status, started_at, finished_at, stats, error
                FROM crawl_runs ORDER BY started_at DESC LIMIT 20
                """
            ).fetchall()
        finally:
            conn.close()
        cols = ["id", "source", "kind", "status", "started_at", "finished_at", "stats", "error"]
        runs = [dict(zip(cols, r)) for r in rows]
        return {"ok": True, "runs": runs}

    @app.get("/llm/models")
    async def llm_models(request: Request):
        if not _authorized(request):
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        conn = conn_factory()
        try:
            settings = get_settings(conn)
        finally:
            conn.close()
        with Client(timeout=15) as client:
            models = list_models(settings, client)
        return {"ok": True, "models": models}

    return app
