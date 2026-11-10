"""GLM 5.3 Flash(thinking off) 1건 스모크: 설정 저장 → 실제 요약 1회."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx  # noqa: E402

from aic.config import load_config  # noqa: E402
from aic.db import connect  # noqa: E402
from aic.enrich.llm_client import LlmSettings, get_settings, save_settings  # noqa: E402
from aic.enrich.summarizer import run_enrichment  # noqa: E402
from aic.sources.github_source import GithubSource  # noqa: E402


def main() -> None:
    cfg = load_config()
    settings = LlmSettings(
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key,
        model="z-ai/glm-5.3-flash",
        extra={"chat_template_kwargs": {"thinking": False}},
    )
    conn = connect(cfg.database_url)
    save_settings(conn, settings)
    conn.commit()
    saved = get_settings(conn)
    print(f"[settings] model={saved.model} extra={saved.extra}")

    src = GithubSource(httpx.Client(timeout=60), token=cfg.github_token, queries=[])
    stats = run_enrichment(conn, settings, limit=1, readme_fetcher=src.fetch_readme)
    conn.commit()
    print(f"[enrich] {stats}")

    row = conn.execute(
        "SELECT slug, canonical_name, category, summary_ko, usage_ko, install_commands, tags"
        " FROM entries WHERE summary_ko IS NOT NULL ORDER BY stars DESC LIMIT 1"
    ).fetchone()
    if row:
        print(f"[sample] {row[0]} | {row[2]} | tags={row[6]}")
        print(f"[summary] {(row[3] or '')[:300]}")
        print(f"[usage] {(row[4] or '')[:200]}")
        print(f"[install] {row[5]}")


if __name__ == "__main__":
    main()
