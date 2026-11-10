"""skills.sh 폴백 어댑터 — SSR 리더보드 HTML 파싱.

API가 Vercel OIDC를 요구하므로(무인증 401), MVP에서는 공개 페이지의
리더보드 마크업을 파싱한다. owner/repo/slug 3-세그먼트 링크만 수집하고,
site/{domain} 같은 well-known 소스는 스킵한다.
"""
import re

import httpx

from aic.models import RawItem
from aic.sources.base import SourceAdapter
from aic.sources.github_source import polite_get

_SKILLS_SH_URL = "https://skills.sh"

_SKIP_OWNERS = {
    "site", "topic", "agent", "agents", "docs", "official", "audits",
    "packs", "trending", "hot", "api",
}

_ANCHOR = re.compile(r'href="(/[^"#?]+)"')
_SUFFIXED_NUM = re.compile(r">\s*([0-9][0-9.,]*\s*[KMB])\s*<")
_PLAIN_NUM = re.compile(r">\s*([0-9][0-9.,]{3,})\s*<")
_NAME_IN_WINDOW = re.compile(r"<h[1-4][^>]*>(.*?)</h[1-4]>", re.S)
_TAGS = re.compile(r"<[^>]+>")

_SUFFIX = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def parse_compact_number(text: str) -> int | None:
    """'4.3M' / '959.7K' / '1,102,400' / '8420' → int. 실패 시 None."""
    t = text.strip().replace(",", "")
    if not t:
        return None
    mult = 1
    if t[-1].upper() in _SUFFIX:
        mult = _SUFFIX[t[-1].upper()]
        t = t[:-1]
    try:
        return int(float(t) * mult)
    except ValueError:
        return None


def _parse_leaderboard(html: str) -> list[RawItem]:
    items: list[RawItem] = []
    seen: set[str] = set()
    anchors = list(_ANCHOR.finditer(html))

    for idx, m in enumerate(anchors):
        parts = [p for p in m.group(1).split("/") if p]
        if len(parts) != 3:
            continue
        owner, repo, slug = parts
        if owner in _SKIP_OWNERS or "." in repo:
            continue
        key = f"{owner}/{repo}/{slug}"
        if key in seen:
            continue
        seen.add(key)

        next_start = anchors[idx + 1].start() if idx + 1 < len(anchors) else len(html)
        window = html[m.end(): min(m.end() + 3000, next_start)]
        nm = _NAME_IN_WINDOW.search(window)
        name = _TAGS.sub("", nm.group(1)).strip() if nm else slug
        im = _SUFFIXED_NUM.search(window) or _PLAIN_NUM.search(window)
        installs = parse_compact_number(im.group(1)) if im else None

        items.append(
            RawItem(
                source="skills_sh",
                external_id=key,
                payload={
                    "owner": owner,
                    "repo": repo,
                    "slug": slug,
                    "name": name,
                    "installs": installs,
                    "repo_url": f"https://github.com/{owner}/{repo}".lower(),
                },
            )
        )
    return items


class SkillsShSource(SourceAdapter):
    source_name = "skills_sh"

    def __init__(self, client: httpx.Client, mode: str = "html",
                 base_url: str = _SKILLS_SH_URL):
        if mode not in ("html", "oidc"):
            raise ValueError(f"unknown mode: {mode}")
        self.client = client
        self.mode = mode
        self.base_url = base_url.rstrip("/")

    def fetch(self) -> list[RawItem]:
        if self.mode == "oidc":
            # 확장점: Vercel OIDC 토큰으로 /api/v1/skills 를 사용하는 경로.
            # 인프라(팀/프로젝트 연결)가 필요해 폴백 먼저. 준비되면 여기 구현.
            raise NotImplementedError("skills.sh OIDC mode is not implemented yet")

        resp = polite_get(self.client, f"{self.base_url}/")
        if resp.status_code != 200:
            return []
        return _parse_leaderboard(resp.text)
