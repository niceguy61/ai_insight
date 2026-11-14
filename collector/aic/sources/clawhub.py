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
        items.extend(self._fetch_skills())
        items.extend(self._fetch_plugins())
        return items

    def _fetch_skills(self) -> list[RawItem]:
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

    def _fetch_plugins(self) -> list[RawItem]:
        """플러그인 디렉터리(/api/v1/plugins) — 공식 채널·커뮤니티 플러그인.

        스킬 목록과 별도 페이지다. 이름이 '@scope/name'이면 scope를 떼고,
        평문 이름이면 소유자를 앞에 붙여 스킬과 같은 'owner/name' 형태로 만든다.
        """
        items: list[RawItem] = []
        seen: set[str] = set()
        cursor: str | None = None

        while True:
            params: dict[str, str] = {"sort": "downloads", "limit": str(PAGE_SIZE)}
            if cursor:
                params["cursor"] = cursor
            resp = polite_get(self.client, f"{self.base_url}/api/v1/plugins", params=params)
            if resp.status_code == 429:
                return items  # 정상 종료
            if resp.status_code != 200:
                break
            data = resp.json()
            for row in data.get("items", []):
                owner = row.get("ownerHandle")
                name = row.get("name") or ""
                if not owner or not name:
                    continue
                ext_id = name[1:] if name.startswith("@") else f"{owner}/{name}"
                ext_id = ext_id.strip().lower()
                if not ext_id or ext_id in seen:
                    continue
                seen.add(ext_id)
                payload = dict(row)
                stats = row.get("stats") or {}
                downloads = stats.get("downloads")
                installs = stats.get("installs")
                payload["installs"] = max(
                    (v for v in (downloads, installs) if v is not None),
                    default=None,
                )
                payload["plugin"] = True
                runtime_id = row.get("runtimeId") or ""
                payload["canonical_url"] = f"{self.base_url}/{owner}/plugins/{runtime_id}".rstrip("/")
                items.append(RawItem(source=self.source_name, external_id=ext_id, payload=payload))
            cursor = data.get("nextCursor")
            if not cursor or len(items) >= MAX_ITEMS:
                break
        return items
