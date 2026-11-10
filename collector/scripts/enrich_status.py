"""요약 대기 항목 수 확인 (admin의 LLM 요약이 처리할 대상)."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

from aic.config import load_config  # noqa: E402
from aic.db import connect  # noqa: E402


def main() -> None:
    conn = connect(load_config().database_url)
    q = lambda s: conn.execute(s).fetchone()[0]

    total = q("SELECT count(*) FROM entries WHERE entry_status='active'")
    summarized = q("SELECT count(*) FROM entries WHERE summary_ko IS NOT NULL")
    short_done = q("SELECT count(*) FROM entries WHERE summary_short_ko IS NOT NULL")
    # enrich가 실제 고르는 대상 (stars>=50 OR installs>=100 중 미완)
    pending = q("""
        SELECT count(*) FROM entries
        WHERE entry_status='active' AND repo_url IS NOT NULL
          AND (COALESCE(stars,0) >= 50 OR COALESCE(installs,0) >= 100)
          AND (summary_ko IS NULL OR summary_short_ko IS NULL OR readme_hash IS NULL)
    """)
    eligible = q("""
        SELECT count(*) FROM entries
        WHERE entry_status='active' AND repo_url IS NOT NULL
          AND (COALESCE(stars,0) >= 50 OR COALESCE(installs,0) >= 100)
    """)

    print(f"전체 엔트리: {total}")
    print(f"요약 대상 (스타50+/설치100+): {eligible}")
    print(f"  └ 완료: {summarized} (한줄 {short_done})")
    print(f"  └ 대기: {pending}  ← 'LLM 요약' 실행 시 이것만 처리")
    print(f"LLM 처리 속도: 항목당 약 1분 → 대기 {pending}건 ≈ {pending}분")


if __name__ == "__main__":
    main()
