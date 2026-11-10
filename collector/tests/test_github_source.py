import json
from datetime import datetime, timezone

import httpx
import pytest

from aic.models import RawItem
from aic.sources.base import SourceAdapter
from aic.sources.github_source import GithubSource


def _search_body(names):
    return {
        "total_count": len(names),
        "incomplete_results": False,
        "items": [
            {
                "full_name": n,
                "name": n.split("/")[1],
                "description": f"desc of {n}",
                "stargazers_count": 10,
                "topics": ["mcp"],
                "license": {"spdx_id": "mit"},
                "homepage": "",
                "created_at": "2026-01-01T00:00:00Z",
                "pushed_at": "2026-11-01T00:00:00Z",
            }
            for n in names
        ],
    }


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_paginates_two_pages():
    calls = {"search": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.github.com"
        assert "search/repositories" in request.url.path
        calls["search"] += 1
        if request.url.params["page"] == "1":
            return httpx.Response(
                200, json=_search_body(["a/one", "b/two"]),
                headers={"X-RateLimit-Remaining": "4000"},
            )
        return httpx.Response(
            200, json=_search_body(["c/three"]),
            headers={"X-RateLimit-Remaining": "3999"},
        )

    src = GithubSource(
        _client(handler), token=None, queries=["topic:mcp-server"],
        max_per_query=1000, per_page=2,
    )
    items = src.fetch()
    assert [i.external_id for i in items] == ["a/one", "b/two", "c/three"]
    assert calls["search"] == 2
    assert all(isinstance(i, RawItem) and i.source == "github" for i in items)


def test_polite_get_retries_after_429_then_succeeds():
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="slow down")
        return httpx.Response(200, json=_search_body(["a/one"]),
                              headers={"X-RateLimit-Remaining": "4000"})

    src = GithubSource(_client(handler), queries=["topic:mcp"], per_page=2)
    items = src.fetch()
    assert [i.external_id for i in items] == ["a/one"]
    assert state["n"] == 2  # 429 후 1회 재시도


def test_polite_get_retries_github_403_rate_limit():
    """GitHub은 rate limit을 403 + X-RateLimit-Remaining: 0 으로도 반환한다."""
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(
                403,
                headers={"X-RateLimit-Remaining": "0", "Retry-After": "0"},
                text="rate limit exceeded",
            )
        return httpx.Response(200, json=_search_body(["a/one"]),
                              headers={"X-RateLimit-Remaining": "4000"})

    src = GithubSource(_client(handler), queries=["topic:mcp"], per_page=2)
    items = src.fetch()
    assert [i.external_id for i in items] == ["a/one"]
    assert state["n"] == 2


def test_polite_get_does_not_retry_plain_403():
    """403이라도 rate limit 표시가 없으면 재시도하지 않는다 (권한 오류일 수 있음)."""
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        return httpx.Response(403, text="forbidden")

    src = GithubSource(_client(handler), queries=["topic:mcp"], per_page=2)
    items = src.fetch()
    assert items == []
    assert state["n"] == 1  # 재시도 없음


def test_fetch_returns_empty_on_persistent_429():
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "0"}, text="slow down")

    src = GithubSource(_client(handler), queries=["topic:mcp"], per_page=2)
    items = src.fetch()  # 예외 없이 정상 반환
    assert items == []
    assert state["n"] == 2  # 재시도 1회 포함


def test_fetch_star_history_parses_starred_at():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/owner/repo/stargazers"
        assert request.headers["accept"] == "application/vnd.github.star+json"
        return httpx.Response(200, json=[
            {"starred_at": "2026-11-09T00:00:00Z", "user": {"login": "u1"}},
            {"starred_at": "2026-11-05T12:00:00Z", "user": {"login": "u2"}},
        ])

    src = GithubSource(_client(handler), queries=[])
    stamps = src.fetch_star_history("owner/repo")
    assert stamps == [
        datetime(2026, 11, 9, tzinfo=timezone.utc),
        datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc),
    ]


def test_fetch_readme_404_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "raw.githubusercontent.com"
        if request.url.path.startswith("/owner/no-readme/"):
            return httpx.Response(404, text="Not Found")
        if request.url.path == "/owner/repo/HEAD/README.md":
            return httpx.Response(200, text="# Hello")
        return httpx.Response(404, text="Not Found")

    src = GithubSource(_client(handler), queries=[])
    assert src.fetch_readme("owner/repo") == "# Hello"
    assert src.fetch_readme("owner/no-readme") is None


def test_fetch_readme_picks_common_variant_when_default_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/owner/repo/HEAD/README.md":
            return httpx.Response(404, text="Not Found")
        if request.url.path == "/owner/repo/HEAD/readme.md":
            return httpx.Response(200, text="# lowercase readme")
        return httpx.Response(404, text="Not Found")

    src = GithubSource(_client(handler), queries=[])
    assert src.fetch_readme("owner/repo") == "# lowercase readme"


def test_low_rate_limit_stops_collection():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_search_body(["a/one"]),
                              headers={"X-RateLimit-Remaining": "3"})

    src = GithubSource(_client(handler), queries=["q1", "q2"], per_page=2)
    items = src.fetch()
    assert [i.external_id for i in items] == ["a/one"]  # 첫 쿼리 1개만 수집하고 중단


def test_github_source_is_source_adapter():
    assert issubclass(GithubSource, SourceAdapter)
