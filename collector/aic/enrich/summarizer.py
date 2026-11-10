"""README → 한국어 요약·사용법·설치법·태그·카테고리 파이프라인.

- 요약 대상: 스타 50+ 또는 설치 100+ 엔트리 (run_enrichment 파라미터로 조절)
- LLM 결과는 llm_cache(입력 해시)에 적재되어 동일 입력 재호출이 없다
- LLM/JSON 실패 시 해당 엔트리만 스킵 — 요약 없이도 원문 링크로 공개된다
"""
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field

from psycopg import Connection

from aic.enrich.llm_client import LlmError, LlmSettings, chat_json
from aic.models import RawItem
from aic.store import insert_raw_item

README_MAX_CHARS = 20_000
SUMMARY_MIN_STARS = 50
SUMMARY_MIN_INSTALLS = 100

CATEGORY_TAXONOMY: list[str] = [
    "검색·브라우저",
    "파일·문서",
    "데이터베이스",
    "개발자 도구",
    "이미지·영상",
    "메모리·컨텍스트",
    "에이전트 프레임워크",
    "클라우드·인프라",
    "생산성",
    "기타",
]

_SYSTEM_PROMPT = """당신은 한국어 AI 에이전트 도구 포털의 큐레이터입니다.
주어진 프로젝트 정보와 README를 읽고 아래 JSON만 출력하세요 (다른 텍스트 금지):
{
  "summary_short_ko": "한 줄 요약 — 반드시 20자 이내, 명사형 종결",
  "summary_ko": "이것이 무엇인지 한국어 3~5문장 요약",
  "usage_ko": "어떻게 쓰는지 한국어 1~3문장",
  "install_commands": [{"target": "claude-code|cursor|codex|opencode|shell 중 하나", "cmd": "실제 설치 명령"}],
  "tags": ["짧은 태그 (한국어/영어 혼용 가능, 최대 8개)"],
  "category": "아래 목록 중 정확히 하나"
}
카테고리 목록: %s

규칙:
- summary_short_ko는 20자를 넘기면 안 됩니다 (예: "노션 데이터베이스를 읽고 쓰는 MCP 서버")
- README에 설치 명령이 있으면 문자 그대로 추출하고, 없으면 빈 배열
- 추측으로 설치법을 만들어내지 마세요
- README가 없으면 이름과 설명만으로 요약하고 불확실함을 드러내세요""" % ", ".join(CATEGORY_TAXONOMY)


@dataclass
class SummaryResult:
    summary_short_ko: str
    summary_ko: str
    usage_ko: str
    install_commands: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    category: str = "기타"


def _normalize_result(raw: dict) -> SummaryResult:
    category = raw.get("category") or "기타"
    if category not in CATEGORY_TAXONOMY:
        category = "기타"
    cmds = raw.get("install_commands") or []
    tags = raw.get("tags") or []
    summary_ko = str(raw.get("summary_ko") or "").strip()
    short = str(raw.get("summary_short_ko") or "").strip() or summary_ko[:22]
    return SummaryResult(
        summary_short_ko=short,
        summary_ko=summary_ko,
        usage_ko=str(raw.get("usage_ko") or "").strip(),
        install_commands=[c for c in cmds if isinstance(c, dict) and c.get("cmd")],
        tags=[str(t).strip() for t in tags if str(t).strip()][:8],
        category=category,
    )


def select_pending(
    conn: Connection,
    limit: int = 100,
    min_stars: int = SUMMARY_MIN_STARS,
    min_installs: int = SUMMARY_MIN_INSTALLS,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, slug, canonical_name, kind, repo_url, stars, installs, summary_ko, summary_short_ko, readme_hash
        FROM entries
        WHERE entry_status = 'active'
          AND repo_url IS NOT NULL
          AND (COALESCE(stars, 0) >= %s OR COALESCE(installs, 0) >= %s)
          AND (summary_ko IS NULL OR summary_short_ko IS NULL OR readme_hash IS NULL)
        ORDER BY stars DESC NULLS LAST, installs DESC NULLS LAST
        LIMIT %s
        """,
        (min_stars, min_installs, limit),
    ).fetchall()
    cols = ["id", "slug", "canonical_name", "kind", "repo_url", "stars",
            "installs", "summary_ko", "summary_short_ko", "readme_hash"]
    return [dict(zip(cols, r)) for r in rows]


def build_prompt(entry: dict, readme: str | None) -> tuple[str, str]:
    """(system, user) 프롬프트 생성. README는 20KB 절단."""
    lines = [
        f"이름: {entry.get('canonical_name')}",
        f"slug: {entry.get('slug')}",
        f"종류: {entry.get('kind')}",
        f"repo: {entry.get('repo_url') or '없음'}",
        "",
        "README:",
    ]
    if readme:
        truncated = readme[:README_MAX_CHARS]
        if len(readme) > README_MAX_CHARS:
            truncated += "\n... (이하 잘림)"
        lines.append(truncated)
    else:
        lines.append("(README를 가져오지 못했습니다)")
    return _SYSTEM_PROMPT, "\n".join(lines)


def apply_summary(conn: Connection, entry_id: uuid.UUID, result: SummaryResult, readme_hash: str) -> None:
    conn.execute(
        """
        UPDATE entries SET
            summary_short_ko = %s, summary_ko = %s, usage_ko = %s, install_commands = %s,
            tags = %s, category = %s, readme_hash = %s
        WHERE id = %s
        """,
        (
            result.summary_short_ko or None, result.summary_ko or None, result.usage_ko or None,
            json.dumps(result.install_commands), result.tags,
            result.category, readme_hash, entry_id,
        ),
    )


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get_readme(conn: Connection, entry: dict, readme_fetcher) -> str | None:
    """raw_items 캐시 우선, 없으면 fetcher로 받아 캐시."""
    slug = entry["slug"]
    row = conn.execute(
        """
        SELECT payload FROM raw_items
        WHERE source='github_readme' AND external_id=%s AND expires_at > now()
        ORDER BY fetched_at DESC LIMIT 1
        """,
        (slug,),
    ).fetchone()
    if row and row[0].get("content"):
        return row[0]["content"]
    if readme_fetcher is None:
        return None
    text = readme_fetcher(slug)
    if text:
        insert_raw_item(conn, RawItem("github_readme", slug, {"content": text}))
    return text


def run_enrichment(
    conn: Connection,
    settings: LlmSettings,
    limit: int = 100,
    readme_fetcher=None,
    llm_client=None,
    min_stars: int = SUMMARY_MIN_STARS,
    min_installs: int = SUMMARY_MIN_INSTALLS,
    commit_each: bool = False,
) -> dict:
    stats = {"summarized": 0, "cache_hits": 0, "failed": 0}

    for entry in select_pending(conn, limit=limit, min_stars=min_stars, min_installs=min_installs):
        readme = _get_readme(conn, entry, readme_fetcher)
        readme_hash = _fingerprint(readme or "")
        if entry["summary_ko"] and entry["summary_short_ko"] and entry["readme_hash"] == readme_hash:
            continue  # 변화 없음

        system, user = build_prompt(entry, readme)
        input_hash = _fingerprint(f"{settings.model}\n{system}\n{user}")

        cached = conn.execute(
            "SELECT output FROM llm_cache WHERE input_hash = %s", (input_hash,)
        ).fetchone()
        try:
            if cached:
                result = _normalize_result(cached[0])
                stats["cache_hits"] += 1
            else:
                raw = chat_json(settings, system, user, client=llm_client)
                result = _normalize_result(raw)
                conn.execute(
                    """
                    INSERT INTO llm_cache (input_hash, model, kind, output)
                    VALUES (%s, %s, 'summary', %s)
                    ON CONFLICT (input_hash) DO NOTHING
                    """,
                    (input_hash, settings.model, json.dumps(asdict(result), ensure_ascii=False)),
                )
        except LlmError:
            stats["failed"] += 1
            continue

        apply_summary(conn, entry["id"], result, readme_hash)
        stats["summarized"] += 1
        if commit_each:
            conn.commit()  # 하나가 끝날 때마다 웹에 바로 보이도록

    return stats
