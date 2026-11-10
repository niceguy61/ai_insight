"""npm registry 검색 어댑터 — MCP 서버 배포 패키지 + 월 다운로드수."""
import httpx

from aic.merge import normalize_repo_url
from aic.models import RawItem
from aic.sources.base import SourceAdapter
from aic.sources.github_source import polite_get

NPM_SEARCH_URL = "https://registry.npmjs.org/-/v1/search"
PAGE_SIZE = 250


class NpmSource(SourceAdapter):
    source_name = "npm"

    def __init__(self, client: httpx.Client, keywords: tuple[str, ...] = ("mcp-server", "mcp")):
        self.client = client
        self.keywords = keywords

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()

        for keyword in self.keywords:
            resp = polite_get(
                self.client,
                NPM_SEARCH_URL,
                params={"text": keyword, "size": str(PAGE_SIZE)},
            )
            if resp.status_code == 429:
                return items  # 정상 종료
            if resp.status_code != 200:
                continue
            for obj in resp.json().get("objects", []):
                package = obj.get("package", {})
                name = package.get("name")
                if not name or name in seen:
                    continue
                seen.add(name)
                payload = {
                    "package": package,
                    "downloads": obj.get("downloads", {}),
                    "searchScore": obj.get("searchScore"),
                }
                links = package.get("links") or {}
                payload["repo_url"] = normalize_repo_url(links.get("repository"))
                items.append(RawItem(source=self.source_name, external_id=name, payload=payload))
        return items
