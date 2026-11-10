"""스케줄러 — 기본 주기(설계 문서 §5.2)로 run_job을 돌린다."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from aic.jobs import delete_expired_raw_items, run_job
from aic.snapshots import recompute_deltas

log = logging.getLogger(__name__)


def _job(conn_factory, name):
    def _run():
        conn = conn_factory()
        try:
            if name == "deltas":
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
                      id=f"source_{name}", max_instances=1, coalesce=True)
    sched.add_job(_job(conn_factory, "deltas"), "interval", hours=1,
                  id="deltas", max_instances=1, coalesce=True)
    sched.add_job(_job(conn_factory, "raw_cleanup"), "interval", hours=24,
                  id="raw_cleanup", max_instances=1, coalesce=True)
    return sched
