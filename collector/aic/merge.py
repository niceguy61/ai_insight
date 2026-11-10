"""repo URL 정규화와 엔트리 슬러그 규칙.

같은 GitHub 리포지토리가 소스마다 다른 형태로 표기되므로, 모든 병합 판정은
여기서 만든 정규형(https://github.com/owner/repo) 하나를 기준으로 한다.
"""
import re
from urllib.parse import urlsplit

_SCP_LIKE = re.compile(r"^git@github\.com:([^/:]+)/(.+)$")
_GITHUB_HOSTS = {"github.com", "www.github.com"}


def _finish(owner: str, repo: str) -> str | None:
    owner = owner.strip().rstrip("/").lower()
    repo = repo.strip().lower()
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    repo = repo.rstrip("/")
    if not owner or not repo or "/" in repo:
        return None
    return f"https://github.com/{owner}/{repo}"


def normalize_repo_url(url: str | None) -> str | None:
    """GitHub repo URL을 https://github.com/owner/repo 소문자 정규형으로 변환.

    GitHub이 아니거나 해석할 수 없으면 None.
    """
    if not url or not url.strip():
        return None
    u = url.strip()

    scp = _SCP_LIKE.match(u)
    if scp:
        return _finish(scp.group(1), scp.group(2))

    if "://" not in u:
        u = "https://" + u.lstrip("/")

    parsed = urlsplit(u)
    host = (parsed.hostname or "").lower()
    if host not in _GITHUB_HOSTS:
        return None

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    return _finish(parts[0], parts[1])


def entry_slug(owner: str, name: str) -> str:
    return f"{owner.strip().lower()}/{name.strip().lower()}"
