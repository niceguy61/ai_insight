import json
import pathlib

import httpx
import pytest

from aic.sources.clawhub import ClawhubSource
from aic.sources.skills_sh import SkillsShSource, parse_compact_number

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def test_parse_compact_number():
    assert parse_compact_number("4.3M") == 4_300_000
    assert parse_compact_number("959.7K") == 959_700
    assert parse_compact_number("1,102,400") == 1_102_400
    assert parse_compact_number("8420") == 8_420
    assert parse_compact_number("2.1B") == 2_100_000_000
    assert parse_compact_number("n/a") is None


def test_skills_sh_html_fallback_parses_leaderboard():
    html = (FIXTURES / "skills_sh_leaderboard.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "skills.sh"
        assert request.url.path == "/"
        return httpx.Response(200, text=html)

    src = SkillsShSource(httpx.Client(transport=httpx.MockTransport(handler)), mode="html")
    items = src.fetch()

    by_id = {i.external_id: i for i in items}
    # site/ 도메인 소스는 스킵되어야 한다
    assert "site/open.feishu.cn/lark-doc" not in by_id
    assert set(by_id) == {
        "vercel-labs/skills/find-skills",
        "mattpocock/skills/grill-me",
        "anthropics/skills/frontend-design",
    }
    first = by_id["vercel-labs/skills/find-skills"]
    assert first.source == "skills_sh"
    assert first.payload["name"] == "find-skills"
    assert first.payload["installs"] == 4_300_000
    assert first.payload["repo_url"] == "https://github.com/vercel-labs/skills"
    assert by_id["mattpocock/skills/grill-me"].payload["installs"] == 959_700
    assert by_id["anthropics/skills/frontend-design"].payload["installs"] == 1_102_400


def test_skills_sh_oidc_mode_is_explicit_extension_point():
    src = SkillsShSource(httpx.Client(), mode="oidc")
    with pytest.raises(NotImplementedError):
        src.fetch()


def test_clawhub_follows_cursor_two_pages():
    page1 = {
        "items": [
            {"ownerHandle": "steipete", "slug": "gifgrep", "displayName": "GifGrep",
             "summary": "Grep gifs", "topics": ["Productivity"],
             "stats": {"downloads": 12000}},
            {"ownerHandle": "openclaw", "slug": "duckduckgo-plugin",
             "displayName": "DuckDuckGo", "summary": "web search",
             "topics": [], "stats": {"downloads": 29400}},
        ],
        "nextCursor": "abc",
    }
    page2 = {
        "items": [
            {"ownerHandle": "openclaw", "slug": "lobster", "displayName": "Lobster",
             "summary": "workflows", "topics": [], "stats": {}},
        ],
        "nextCursor": None,
    }
    plugin_page = {
        "items": [
            {"ownerHandle": "openclaw", "name": "@openclaw/whatsapp",
             "displayName": "WhatsApp", "summary": "WhatsApp channel plugin",
             "runtimeId": "whatsapp", "stats": {"downloads": 208924, "installs": 1171}},
            {"ownerHandle": "sider", "name": "chrome-openclaw-sider",
             "displayName": "Sider", "summary": "browser plugin",
             "runtimeId": "chrome-openclaw-sider", "stats": {"downloads": 20730}},
        ],
        "nextCursor": None,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "clawhub.example"
        assert request.url.params["sort"] == "downloads"
        if request.url.path == "/api/v1/plugins":
            return httpx.Response(200, json=plugin_page)
        assert request.url.path == "/api/v1/skills"
        if "cursor" not in request.url.params:
            return httpx.Response(200, json=page1)
        assert request.url.params["cursor"] == "abc"
        return httpx.Response(200, json=page2)

    src = ClawhubSource(httpx.Client(transport=httpx.MockTransport(handler)),
                        base_url="https://clawhub.example")
    items = src.fetch()
    ids = [i.external_id for i in items]
    assert ids == [
        "steipete/gifgrep", "openclaw/duckduckgo-plugin", "openclaw/lobster",
        "openclaw/whatsapp", "sider/chrome-openclaw-sider",
    ]
    assert items[0].payload["installs"] == 12000
    assert items[2].payload["installs"] is None  # stats 비어 있으면 None
    # 플러그인 표식과 설치수(다운로드·설치 중 큰 값)
    assert items[3].payload["plugin"] is True
    assert items[3].payload["installs"] == 208924
    assert items[4].payload["plugin"] is True
    assert items[4].payload["installs"] == 20730


def test_clawhub_plugin_slug_strips_scope_and_merges_duplicates():
    plugin_page = {
        "items": [
            {"ownerHandle": "openclaw", "name": "@openclaw/WhatsApp",
             "displayName": "WhatsApp", "runtimeId": "whatsapp",
             "stats": {"downloads": 100}},
            {"ownerHandle": "openclaw", "name": "@openclaw/whatsapp",
             "displayName": "WhatsApp dup", "runtimeId": "whatsapp",
             "stats": {"downloads": 100}},
        ],
        "nextCursor": None,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        # fetch()는 스킬과 플러그인을 모두 긁는다 — 스킬은 빈 목록으로 응답
        if request.url.path == "/api/v1/skills":
            return httpx.Response(200, json={"items": [], "nextCursor": None})
        assert request.url.path == "/api/v1/plugins"
        return httpx.Response(200, json=plugin_page)

    src = ClawhubSource(httpx.Client(transport=httpx.MockTransport(handler)),
                        base_url="https://clawhub.example")
    items = src.fetch()
    assert [i.external_id for i in items] == ["openclaw/whatsapp"]
