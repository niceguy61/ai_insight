"""GraphQL로 stargazers starred_at 조회 테스트."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx  # noqa: E402

from aic.config import load_config  # noqa: E402

QUERY = """
query {
  repository(owner: "n8n-io", name: "n8n") {
    stargazerCount
    stargazers(first: 5, orderBy: {field: STARRED_AT, direction: ASC}) {
      edges { starredAt }
      pageInfo { endCursor hasNextPage }
    }
  }
}
"""


def main() -> None:
    cfg = load_config()
    tok = (cfg.github_token or "").strip()
    r = httpx.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"Bearer {tok}"},
        json={"query": QUERY},
    )
    print("GraphQL:", r.status_code)
    data = r.json()
    if data.get("errors"):
        print("errors:", [e.get("message", "")[:100] for e in data["errors"]])
    if data.get("data") and data["data"].get("repository"):
        repo = data["data"]["repository"]
        print("stargazerCount:", repo["stargazerCount"])
        print("첫 5개 starred_at:", [e["starredAt"][:10] for e in repo["stargazers"]["edges"]])
        print("hasNextPage:", repo["stargazers"]["pageInfo"]["hasNextPage"])


if __name__ == "__main__":
    main()
