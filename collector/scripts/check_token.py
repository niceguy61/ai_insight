"""토큰 유효성 단계 진단: /rate_limit → /user → /repos → stargazers."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx  # noqa: E402

from aic.config import load_config  # noqa: E402


def main() -> None:
    cfg = load_config()
    token = (cfg.github_token or "").strip()
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    with httpx.Client(timeout=30) as c:
        r1 = c.get("https://api.github.com/rate_limit", headers=h)
        print(f"1) /rate_limit: {r1.status_code}")
        if r1.status_code == 200:
            core = r1.json()["resources"]["core"]
            print(f"   core remaining: {core['remaining']}/{core['limit']}")

        r2 = c.get("https://api.github.com/user", headers=h)
        print(f"2) /user: {r2.status_code}", r2.json().get("login", r2.json().get("message", ""))[:60])

        r3 = c.get("https://api.github.com/repos/n8n-io/n8n", headers=h)
        print(f"3) /repos/n8n-io/n8n: {r3.status_code}", r3.json().get("message", "")[:60])

        h4 = dict(h, Accept="application/vnd.github.star+json")
        r4 = c.get("https://api.github.com/repos/n8n-io/n8n/stargazers?per_page=3&page=1", headers=h4)
        print(f"4) stargazers: {r4.status_code}", r4.json().get("message", "")[:60] if r4.status_code != 200 else "OK")
        if r4.status_code == 200:
            print("   starred_at:", all("starred_at" in i for i in r4.json()))

        # 토큰 앞뒤 공백/따옴표 여부 (값 노출 없이)
        raw = token
        print(f"5) 토큰 문자열 진단: 앞공백={raw != raw.lstrip()} 뒤공백={raw != raw.rstrip()} 따옴표={'\"' in raw or chr(39) in raw}")


if __name__ == "__main__":
    main()
