"""GitHub Search API 소스 어댑터.

polite_get은 다른 어댑터(skills.sh, ClawHub 등)도 재사용하는 공통 429 처리다.
"""
import time
from datetime import datetime
from urllib.parse import quote

import httpx

from aic.models import RawItem
from aic.sources.base import SourceAdapter

API_BASE = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"

DEFAULT_QUERIES = [
    "topic:mcp-server",
    "topic:claude-skills",
    "topic:agent-skills",
    "mcp server in:name,description",
    "claude skill in:name,description",
]

README_VARIANTS = ["README.md", "readme.md", "README.markdown", "README.rst", "README"]


def _is_rate_limited(resp: httpx.Response) -> bool:
    """429 또는 GitHub식 403+Remaining:0 (GitHub은 rate limit을 403으로도 반환)."""
    if resp.status_code == 429:
        return True
    return resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0"


def _retry_delay(resp: httpx.Response) -> float:
    raw = resp.headers.get("Retry-After")
    if raw:
        try:
            return min(float(raw), 60.0)
        except ValueError:
            pass
    reset = resp.headers.get("X-RateLimit-Reset")
    if reset:
        try:
            return min(max(float(reset) - time.time(), 0.0), 60.0)
        except ValueError:
            pass
    return 5.0


def polite_get(client: httpx.Client, url: str, **kw) -> httpx.Response:
    """GET 한 번. 429(또는 GitHub식 403 rate limit)면 Retry-After만큼 대기 후 1회 재시도.

    재시도 후에도 막히면 마지막 응답을 그대로 돌려준다(호출자가 정상 종료 판단).
    """
    resp = client.get(url, **kw)
    if _is_rate_limited(resp):
        time.sleep(_retry_delay(resp))
        resp = client.get(url, **kw)
    return resp


def _remaining(resp: httpx.Response) -> int:
    try:
        return int(resp.headers.get("X-RateLimit-Remaining", "9999"))
    except ValueError:
        return 9999


class GithubSource(SourceAdapter):
    source_name = "github"

    def __init__(
        self,
        client: httpx.Client,
        token: str | None = None,
        queries: list[str] | None = None,
        max_per_query: int = 1000,
        per_page: int = 100,
    ):
        self.client = client
        self.token = token
        self.queries = queries if queries is not None else list(DEFAULT_QUERIES)
        self.max_per_query = max_per_query
        self.per_page = per_page

    def _headers(self, accept: str = "application/vnd.github+json") -> dict[str, str]:
        headers = {"Accept": accept}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        max_pages = max(1, self.max_per_query // self.per_page)

        for q in self.queries:
            for page in range(1, max_pages + 1):
                url = (
                    f"{API_BASE}/search/repositories"
                    f"?q={quote(q)}&sort=stars&order=desc"
                    f"&per_page={self.per_page}&page={page}"
                )
                resp = polite_get(self.client, url, headers=self._headers())
                if resp.status_code == 429:
                    return items  # 정상 종료: 이번 실행은 여기까지
                if resp.status_code != 200:
                    break  # 이 쿼리만 포기
                batch = resp.json().get("items", [])
                if not batch:
                    break
                items.extend(
                    RawItem(source=self.source_name, external_id=it["full_name"], payload=it)
                    for it in batch
                )
                if _remaining(resp) < 5:
                    return items
                if len(batch) < self.per_page:
                    break
        return items

    def fetch_readme(self, full_name: str) -> str | None:
        for variant in README_VARIANTS:
            url = f"{RAW_BASE}/{full_name}/HEAD/{variant}"
            resp = self.client.get(url)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code == 429:
                resp = polite_get(self.client, url)
                if resp.status_code == 200:
                    return resp.text
        return None

    def fetch_star_history(self, full_name: str, max_pages: int = 10) -> list[datetime]:
        stamps: list[datetime] = []
        for page in range(1, max_pages + 1):
            url = f"{API_BASE}/repos/{full_name}/stargazers?per_page=100&page={page}"
            resp = polite_get(self.client, url, headers=self._headers("application/vnd.github.star+json"))
            if resp.status_code != 200:
                break
            batch = resp.json() or []
            for entry in batch:
                starred_at = entry.get("starred_at")
                if starred_at:
                    stamps.append(datetime.fromisoformat(starred_at.replace("Z", "+00:00")))
            if len(batch) < 100:
                break
        return stamps
