"""stargazers starredAt 노출 여부 확인 (orderBy 없음)."""
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
    stargazers(first: 5) {
      edges {
        starredAt
        node { login }
      }
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
    print("status:", r.status_code)
    data = r.json()
    if data.get("errors"):
        print("errors:", [e.get("message", "")[:150] for e in data["errors"]])
    if data.get("data") and data["data"].get("repository"):
        edges = data["data"]["repository"]["stargazers"]["edges"]
        print(f"edges: {len(edges)}")
        for e in edges[:5]:
            print("  ", e)


if __name__ == "__main__":
    main()
