"""ClawHub 공개 API 어댑터.

서드파티 디렉터리 이용이 공식 허용된 읽기 전용 엔드포인트만 사용하고,
429/Retry-After를 준수하며 원본(canonical) 링크를 항상 보존한다.
"""
import httpx

from aic.models import RawItem
from aic.sources.base import SourceAdapter
from aic.sources.github_source import polite_get

DEFAULT_BASE_URL = "https://clawhub.ai"
PAGE_SIZE = 100
MAX_ITEMS = 3000  # downloads 정렬 상위 N개만 — 디렉터리 전체(85k+) 수집 방지


class ClawhubSource(SourceAdapter):
    source_name = "clawhub"

    def __init__(self, client: httpx.Client, base_url: str = DEFAULT_BASE_URL):
        self.client = client
        self.base_url = base_url.rstrip("/")

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        cursor: str | None = None

        while True:
            params: dict[str, str] = {"sort": "downloads", "limit": str(PAGE_SIZE)}
            if cursor:
                params["cursor"] = cursor
            resp = polite_get(self.client, f"{self.base_url}/api/v1/skills", params=params)
            if resp.status_code == 429:
                return items  # 정상 종료
            if resp.status_code != 200:
                break
            data = resp.json()
            for row in data.get("items", []):
                owner = row.get("ownerHandle")
                slug = row.get("slug")
                if not owner or not slug:
                    continue
                ext_id = f"{owner}/{slug}"
                if ext_id in seen:
                    continue
                seen.add(ext_id)
                payload = dict(row)
                stats = row.get("stats") or {}
                payload["installs"] = stats.get("downloads")
                payload["canonical_url"] = f"{self.base_url}/{owner}/skills/{slug}"
                items.append(RawItem(source=self.source_name, external_id=ext_id, payload=payload))
            cursor = data.get("nextCursor")
            if not cursor or len(items) >= MAX_ITEMS:
                break
        return items
