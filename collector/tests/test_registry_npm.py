import httpx

from aic.sources.mcp_registry import McpRegistrySource
from aic.sources.npm_source import NpmSource


def test_mcp_registry_paginates_by_next_cursor():
    page1 = {
        "servers": [
            {"server": {"name": "ac.demo/mcp", "title": "Demo", "description": "d",
                        "version": "1.0.0",
                        "repository": {"url": "https://github.com/ac/demo"}},
             "_meta": {}},
            {"server": {"name": "ac.demo/mcp", "title": "Demo", "description": "d",
                        "version": "0.9.0"},
             "_meta": {}},
        ],
        "metadata": {"nextCursor": "ac.demo/mcp:0.9.0", "count": 2},
    }
    page2 = {
        "servers": [
            {"server": {"name": "ac.other/mcp", "title": "Other", "description": "o",
                        "version": "2.0.0"},
             "_meta": {}},
        ],
        "metadata": {"nextCursor": None, "count": 1},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "registry.example"
        assert request.url.path == "/v0/servers"
        if "cursor" not in request.url.params:
            return httpx.Response(200, json=page1)
        return httpx.Response(200, json=page2)

    src = McpRegistrySource(httpx.Client(transport=httpx.MockTransport(handler)),
                            base_url="https://registry.example")
    items = src.fetch()
    names = [i.external_id for i in items]
    assert names == ["ac.demo/mcp", "ac.other/mcp"]  # 구버전 중복 제거
    assert items[0].source == "mcp_registry"
    assert items[0].payload["repo_url"] == "https://github.com/ac/demo"


def test_npm_search_merges_keywords_and_dedupes():
    kw_page = {
        "mcp-server": {"objects": [
            {"package": {"name": "@scope/notion-mcp-server",
                         "description": "Official MCP server for Notion API",
                         "links": {"repository": "git+ssh://git@github.com/makenotion/notion-mcp-server.git"},
                         "keywords": ["notion", "mcp"]},
             "downloads": {"monthly": 959291}, "searchScore": 380.0},
            {"package": {"name": "tiny-mcp", "description": "t",
                         "links": {}, "keywords": ["mcp"]},
             "downloads": {"monthly": 10}, "searchScore": 1.0},
        ], "total": 2},
        "mcp": {"objects": [
            {"package": {"name": "tiny-mcp", "description": "t",
                         "links": {}, "keywords": ["mcp"]},
             "downloads": {"monthly": 10}, "searchScore": 1.0},
            {"package": {"name": "other-mcp", "description": "o",
                         "links": {"repository": "https://github.com/x/other"},
                         "keywords": ["mcp"]},
             "downloads": {"monthly": 50}, "searchScore": 5.0},
        ], "total": 2},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "registry.npmjs.org"
        assert request.url.path == "/-/v1/search"
        text = request.url.params["text"]
        return httpx.Response(200, json=kw_page[text])

    src = NpmSource(httpx.Client(transport=httpx.MockTransport(handler)))
    items = src.fetch()
    names = sorted(i.external_id for i in items)
    assert names == ["@scope/notion-mcp-server", "other-mcp", "tiny-mcp"]  # 중복 제거
    notion = next(i for i in items if i.external_id == "@scope/notion-mcp-server")
    assert notion.source == "npm"
    assert notion.payload["downloads"]["monthly"] == 959291
    assert notion.payload["repo_url"] == "https://github.com/makenotion/notion-mcp-server"
    assert next(i for i in items if i.external_id == "tiny-mcp").payload["repo_url"] is None
