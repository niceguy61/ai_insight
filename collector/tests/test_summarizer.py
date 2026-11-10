import json
from uuid import uuid4

from aic.enrich.llm_client import LlmSettings
from aic.enrich.summarizer import (
    CATEGORY_TAXONOMY,
    build_prompt,
    run_enrichment,
)
from aic.models import RawItem
from aic.store import insert_raw_item, upsert_entry

SETTINGS = LlmSettings(base_url="https://x/v1", api_key="k", model="test-model")

VALID_JSON = json.dumps({
    "summary_ko": "이 MCP 서버는 노션 데이터베이스를 읽고 씁니다.",
    "usage_ko": "claude mcp add 명령으로 등록한 뒤 사용합니다.",
    "install_commands": [{"target": "claude-code", "cmd": "claude mcp add notion -- npx @notionhq/notion-mcp-server"}],
    "tags": ["노션", "notion", "문서"],
    "category": "생산성",
}, ensure_ascii=False)


class FakeLlm:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    # chat_json이 기대하는 인터페이스
    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls += 1
        return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": self.content})()})()]})()


def _mk_entry(db, slug="owner/repo", stars=100, installs=None):
    return upsert_entry(
        db, RawItem("github", slug, {"name": "Repo"}),
        kind="mcp", repo_url=f"https://github.com/{slug}", stars=stars, installs=installs,
    )


def test_apply_summary_via_run_enrichment(db):
    entry_id = _mk_entry(db)
    llm = FakeLlm(VALID_JSON)

    stats = run_enrichment(db, SETTINGS, limit=10, llm_client=llm)
    assert stats == {"summarized": 1, "cache_hits": 0, "failed": 0}
    assert llm.calls == 1

    row = db.execute(
        "SELECT summary_ko, usage_ko, install_commands, tags, category, readme_hash"
        " FROM entries WHERE id=%s", (entry_id,),
    ).fetchone()
    assert row[0].startswith("이 MCP 서버는")
    assert row[2][0]["cmd"].startswith("claude mcp add")
    assert row[3] == ["노션", "notion", "문서"]
    assert row[4] == "생산성"
    assert row[5] is not None


def test_second_run_hits_cache_without_llm_call(db):
    _mk_entry(db)
    llm = FakeLlm(VALID_JSON)
    run_enrichment(db, SETTINGS, limit=10, llm_client=llm)
    first_calls = llm.calls

    # 요약이 이미 있어 select_pending이 안 고르면 캐시 테스트이므로
    # readme_hash를 지워 다시 pending 상태로 만든다
    db.execute("UPDATE entries SET summary_ko=NULL")
    stats2 = run_enrichment(db, SETTINGS, limit=10, llm_client=llm)
    assert stats2["cache_hits"] == 1
    assert stats2["failed"] == 0
    assert llm.calls == first_calls  # LLM 호출 증가 없음


def test_broken_json_counts_failed_and_entry_stays_public(db):
    entry_id = _mk_entry(db)
    llm = FakeLlm("이것은 전혀 JSON이 아닌 문장입니다")

    stats = run_enrichment(db, SETTINGS, limit=10, llm_client=llm)
    assert stats["failed"] == 1
    assert stats["summarized"] == 0

    summary = db.execute(
        "SELECT summary_ko FROM entries WHERE id=%s", (entry_id,)
    ).fetchone()[0]
    assert summary is None  # 요약 없이도 공개 가능 상태 유지


def test_huge_readme_truncated_to_20kb():
    entry = {"slug": "owner/repo", "canonical_name": "Repo", "kind": "mcp",
             "repo_url": "https://github.com/owner/repo"}
    huge = "".join(f"라인 {i:06d} 한글 readme 내용\n" for i in range(60_000))  # ~1.8MB, 비반복
    system, user = build_prompt(entry, huge)
    assert len(user) < 21_000
    assert huge[:100] in user  # 앞부분은 보존
    assert huge[-100:] not in user  # 끝부분은 잘림


def test_none_readme_still_produces_prompt():
    entry = {"slug": "owner/repo", "canonical_name": "Repo", "kind": "mcp",
             "repo_url": "https://github.com/owner/repo"}
    system, user = build_prompt(entry, None)
    assert "readme" in user.lower() or "README" in user
    assert "Repo" in user


def test_unknown_category_corrected_to_etc(db):
    _mk_entry(db)
    bad = json.loads(VALID_JSON)
    bad["category"] = "없는카테고리"
    llm = FakeLlm(json.dumps(bad, ensure_ascii=False))

    stats = run_enrichment(db, SETTINGS, limit=10, llm_client=llm)
    assert stats["summarized"] == 1
    cat = db.execute("SELECT category FROM entries WHERE summary_ko IS NOT NULL").fetchone()[0]
    assert cat == "기타"


def test_taxonomy_has_ten_categories():
    assert len(CATEGORY_TAXONOMY) == 10
    assert CATEGORY_TAXONOMY[-1] == "기타"


def test_readme_from_raw_items_reused_without_fetch(db):
    entry_id = _mk_entry(db)
    insert_raw_item(db, RawItem("github_readme", "owner/repo", {"content": "# 캐시된 readme"}))

    fetched = []

    def fetcher(slug):
        fetched.append(slug)
        return "# 새로 fetch한 readme"

    llm = FakeLlm(VALID_JSON)
    run_enrichment(db, SETTINGS, limit=10, readme_fetcher=fetcher, llm_client=llm)
    assert fetched == []  # raw_items에 있으니 fetch 안 함

    # raw 항목을 지우면 이번엔 fetcher 사용
    db.execute("DELETE FROM raw_items WHERE source='github_readme'")
    db.execute("UPDATE entries SET summary_ko=NULL WHERE id=%s", (entry_id,))
    run_enrichment(db, SETTINGS, limit=10, readme_fetcher=fetcher, llm_client=llm)
    assert fetched == ["owner/repo"]
