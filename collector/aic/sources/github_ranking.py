"""EvanLi/Github-Ranking 파서 — 전체 Top-100 스타 랭킹 마크다운 표.

이 소스는 entries로 들어가지 않는다(일반 리포라서 MCP·스킬 포털 오염).
rank_reference 표에 스냅샷으로만 쌓이는 레퍼런스 데이터다.
"""
import re

from aic.models import RawItem
from aic.sources.github_source import polite_get

RANKING_URL = (
    "https://raw.githubusercontent.com/EvanLi/Github-Ranking/master/Top100/Top-100-stars.md"
)

# | 1 | [name](https://github.com/owner/repo) | 561391 | 52535 | Markdown | 292 | desc | ... |
_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*\[([^\]]+)\]\((https://github\.com/[^)\s]+)\)\s*"
    r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]*)\|\s*\d+\s*\|\s*([^|]*)\|",
    re.MULTILINE,
)


def parse_ranking(markdown: str) -> list[dict]:
    """마크다운 표에서 {rank, full_name, url, stars, language, description} 목록."""
    out: list[dict] = []
    seen: set[str] = set()
    for m in _ROW.finditer(markdown):
        rank = int(m.group(1))
        url = m.group(3).rstrip("/")
        full_name = url.replace("https://github.com/", "").lower()
        if not full_name or "/" not in full_name or full_name in seen:
            continue
        seen.add(full_name)
        out.append(
            {
                "rank": rank,
                "name": m.group(2).strip(),
                "full_name": full_name,
                "url": url,
                "stars": int(m.group(4)),
                "language": m.group(6).strip() or None,
                "description": m.group(7).strip()[:500],
            }
        )
    return out


def fetch_ranking(client) -> list[dict]:
    """최신 Top-100-stars.md를 받아 파싱. 실패 시 빈 목록."""
    resp = polite_get(client, RANKING_URL)
    if resp.status_code != 200:
        return []
    return parse_ranking(resp.text)
