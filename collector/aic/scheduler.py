"""스케줄러 — 기본 주기(설계 문서 §5.2)로 run_job을 돌린다."""
import logging
import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler

from aic.jobs import delete_expired_raw_items, end_enrich, run_job, try_begin_enrich
from aic.snapshots import recompute_deltas

log = logging.getLogger(__name__)

SWEEP_STALE_RUNS = """
UPDATE crawl_runs
SET status = 'error', finished_at = now(), error = 'interrupted (process restart or crash)'
WHERE status = 'running' AND started_at < now() - interval '2 hours'
"""


def _job(conn_factory, name):
    def _run():
        conn = conn_factory()
        try:
            if name == "deltas":
                # 좀비 run 정리 — 프로세스 크래시로 'running'인 채 남은 행 표시
                cur = conn.execute(SWEEP_STALE_RUNS)
                if cur.rowcount:
                    log.warning("stale running runs marked error: %s", cur.rowcount)
                count = recompute_deltas(conn)
                log.info("deltas job: %s updated", count)
            elif name == "raw_cleanup":
                count = delete_expired_raw_items(conn)
                log.info("raw cleanup: %s deleted", count)
            else:
                stats = run_job(conn, name)
                log.info("%s job: %s", name, stats)
            conn.commit()
        except Exception:
            conn.rollback()
            log.exception("job %s failed", name)
        finally:
            conn.close()
    _run.__name__ = f"job_{name}"
    return _run


def build_scheduler(conn_factory) -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="UTC")
    for name, hours in (("github", 6), ("snapshots", 6),
                        ("skills_sh", 12), ("clawhub", 12),
                        ("mcp_registry", 24), ("npm", 24),
                        ("rank_ref", 24), ("trending", 12)):
        sched.add_job(_job(conn_factory, name), "interval", hours=hours,
                      id=f"source_{name}", max_instances=1, coalesce=True,
                      misfire_grace_time=600, jitter=90)
    sched.add_job(_job(conn_factory, "deltas"), "interval", hours=1,
                  id="deltas", max_instances=1, coalesce=True,
                  misfire_grace_time=600, jitter=90)
    sched.add_job(_job(conn_factory, "raw_cleanup"), "interval", hours=24,
                  id="raw_cleanup", max_instances=1, coalesce=True,
                  misfire_grace_time=600, jitter=90)
    return sched


def start_enrich_worker(conn_factory) -> None:
    """상시 요약 워커 — 켜져 있는 동안 백로그를 쉼 없이 소화한다.

    - 대기 항목이 있으면 200건 배치를 연속 실행 (배치 간 휴식 없음)
    - 백로그가 비면 15분마다 신규 항목을 확인 (수집이 계속 유입되므로 사실상 상시)
    - 중복 방지: crawl_runs에 running enrich가 있으면 이 배치는 건너뜀
      (관리자 수동 실행과의 충돌 방지 — 제어 API 409 가드와 동일 조건)
    """
    def _loop():
        log.info("enrich worker 시작 — 백로그 상시 소화")
        while True:
            try:
                conn = conn_factory()
                try:
                    pending = conn.execute(
                        """
                        SELECT count(*) FROM entries
                        WHERE entry_status = 'active' AND repo_url IS NOT NULL
                          AND (COALESCE(stars,0) >= 50 OR COALESCE(installs,0) >= 100)
                          AND (summary_ko IS NULL OR summary_short_ko IS NULL
                               OR readme_hash IS NULL)
                        """
                    ).fetchone()[0]
                    busy = conn.execute(
                        "SELECT 1 FROM crawl_runs WHERE source='enrich' AND status='running'"
                        " AND started_at > now() - interval '3 hours' LIMIT 1"
                    ).fetchone()
                finally:
                    conn.close()

                if busy:
                    log.info("enrich worker: 다른 enrich 실행 중 — 60초 대기")
                    time.sleep(60)
                    continue
                if pending == 0:
                    log.info("enrich worker: 백로그 없음 — 15분 대기")
                    time.sleep(900)
                    continue

                if not try_begin_enrich():
                    log.info("enrich worker: enrich 락 점유 — 60초 대기")
                    time.sleep(60)
                    continue

                log.info("enrich worker: 대기 %s건 — 배치 실행", f"{pending:,}")
                conn = conn_factory()
                try:
                    run_job(conn, "enrich")
                    conn.commit()
                finally:
                    end_enrich()
                    conn.close()
            except Exception:
                log.exception("enrich worker 오류 — 60초 후 재시도")
                time.sleep(60)

    threading.Thread(target=_loop, daemon=True, name="enrich-worker").start()
