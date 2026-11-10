"""백필 0건 진단: rate limit 상태 + 실제 fetch_star_history 호출 확인."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx  # noqa: E402

from aic.config import load_config  # noqa: E402
from aic.sources.github_source import GithubSource  # noqa: E402


def main() -> None:
    cfg = load_config()
    client = httpx.Client(timeout=30)
    headers = {}
    if cfg.github_token:
        headers["Authorization"] = f"Bearer {cfg.github_token}"

    # 1) rate limit 상태
    r = client.get("https://api.github.com/rate_limit", headers=headers)
    if r.status_code == 200:
        core = r.json()["resources"]["core"]
        search = r.json()["resources"]["search"]
        print(f"core: {core['remaining']}/{core['limit']} (reset {core['reset']})")
        print(f"search: {search['remaining']}/{search['limit']}")
    else:
        print("rate_limit check failed:", r.status_code)

    # 2) stargazers 직접 호출
    gh = GithubSource(client, token=cfg.github_token or None, queries=[])
    stamps = gh.fetch_star_history("n8n-io/n8n", max_pages=3)
    print(f"n8n stamps: {len(stamps)}개, 최근 3개: {[s.isoformat()[:16] for s in stamps[-3:]]}")


if __name__ == "__main__":
    main()
