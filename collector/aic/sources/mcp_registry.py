"""공식 MCP Registry 어댑터.

버전별 행이 여러 개 내려오므로 version=latest 파라미터를 쓰고,
동일 name이 남아 있으면 처음 것만 유지한다(정규화된 repo_url은 payload에).
"""
import httpx

from aic.merge import normalize_repo_url
from aic.models import RawItem
from aic.sources.base import SourceAdapter
from aic.sources.github_source import polite_get

DEFAULT_BASE_URL = "https://registry.modelcontextprotocol.io"
PAGE_SIZE = 100


class McpRegistrySource(SourceAdapter):
    source_name = "mcp_registry"

    def __init__(self, client: httpx.Client, base_url: str = DEFAULT_BASE_URL):
        self.client = client
        self.base_url = base_url.rstrip("/")

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        cursor: str | None = None

        while True:
            params: dict[str, str] = {"limit": str(PAGE_SIZE), "version": "latest"}
            if cursor:
                params["cursor"] = cursor
            resp = polite_get(self.client, f"{self.base_url}/v0/servers", params=params)
            if resp.status_code == 429:
                return items  # 정상 종료
            if resp.status_code != 200:
                break
            data = resp.json()
            for entry in data.get("servers", []):
                server = entry.get("server", {})
                name = server.get("name")
                if not name or name in seen:
                    continue
                seen.add(name)
                payload = dict(server)
                payload["repo_url"] = normalize_repo_url(
                    (server.get("repository") or {}).get("url")
                )
                items.append(
                    RawItem(source=self.source_name, external_id=name, payload=payload)
                )
            cursor = (data.get("metadata") or {}).get("nextCursor")
            if not cursor:
                break
        return items
