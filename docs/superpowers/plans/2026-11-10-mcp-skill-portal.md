# MCP·Skill 포털 (ai_insight) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MCP 서버·에이전트 스킬을 공개 API(GitHub/skills.sh/ClawHub/MCP Registry/npm)에서 수집하고, LLM으로 한국어 요약·설치법·태그를 붙여 랭킹(전체 스타/급상승/신규 급상승/설치수)·검색이 되는 웹 포털을 만든다.

**Architecture:** Next.js 포털 + Python 수집기가 PostgreSQL 하나를 공유. 수집기는 소스 어댑터 → 원문 캐시 → 엔트리 병합 → 스냅샷(급상승) → LLM 정제 파이프라인이고, 웹은 DB를 직접 읽는다. 제어는 collector의 FastAPI control API(ADMIN_TOKEN 게이트)로 한다.

**Tech Stack:** Python 3.12 (httpx, psycopg3, pydantic, APScheduler, FastAPI, openai SDK, pytest) / Next.js 15 + TypeScript + Drizzle ORM (읽기 전용+config 소량 쓰기) / PostgreSQL 17 (Docker Compose)

**Spec:** `docs/superpowers/specs/2026-11-10-mcp-skill-portal-design.md` (함께 읽을 것)

## Global Constraints

- PostgreSQL은 Docker Compose로 구동. 호스트 포트 **5433**, user/pass/db = `insight/insight/insight`
- 모든 키는 `.env`에만 존재. 저장소에 커밋 금지 (`.env.example`만 커밋)
- GitHub 무토큰 시 수집기는 동작하되 저속(요청 사이 sleep 1s). 토큰 있으면 sleep 0.2s
- 모든 소스 어댑터: HTTP 429 → `Retry-After`만큼 대기 후 1회 재시도, 재차 429면 그 소스 실행을 정상 종료(stats에 기록)
- README는 20KB에서 절단 후 LLM 전달
- 수집 상한(config로 조절 가능): GitHub 쿼리당 1,000개, tracked 스냅샷 3,000, LLM 요약 대상 `stars>=50 OR installs>=100`, 요약 100건/run
- LLM 요약 대상 엔트리는 요약 없이도 공개(원문 링크는 항상 표시)
- raw_items TTL 30일, 정리 job이 주기 삭제
- 웹 바인딩 localhost, `/admin`과 control API는 `ADMIN_TOKEN` 헤더 게이트
- UI 언어 한국어, 모든 엔트리 상세에 원문 출처 링크 목록 표시
- 포털 이름은 UI 작업명 `ai_insight` (config로 교체 가능)

## Review Focus

1. **429/Retry-After 위반** — 어댑터가 429를 에러로 처리해 실행이 죽거나, 무시하고 계속 때려 밴되는 상황 → Task 4 테스트로 고정
2. **repo URL 변형 병합 실패** — `https://www.github.com/Owner/Repo/`, `git@github.com:owner/repo.git`이 서로 다른 엔트리로 쪼개지는 상황 → Task 3 테스트로 고정
3. **LLM JSON 오류가 공개 콘텐츠를 죽이는 것** — JSON 파싱 실패 시 해당 엔트리만 스킵되고 요약 없이 공개되어야 함 → Task 9 테스트로 고정
4. **한국어 부분 검색 미작동** — "노션"으로 Notion MCP가 안 찾아지는 상황(pg_trgm 보조) → Task 11 테스트로 고정
5. **빈/유니코드 README·과대 README** — None/한글/1MB README가 요약 파이프라인을 깨는 상황 → Task 9 절단·None 처리 테스트로 고정

---

### Task 1: 저장소 골격 + Docker Compose PostgreSQL

**Files:**
- Create: `docker-compose.yml`, `.gitignore`, `.env.example`, `README.md`

**Interfaces:**
- Produces: `DATABASE_URL=postgresql://insight:insight@localhost:5433/insight` 로 접근 가능한 PostgreSQL 17 (이후 모든 태스크의 전제)

- [ ] **Step 1: 파일 작성**

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: insight
      POSTGRES_PASSWORD: insight
      POSTGRES_DB: insight
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

`.env.example`: `DATABASE_URL`, `DATABASE_URL_TEST`(db명 `insight_test`), `GITHUB_TOKEN`(빈 값), `ADMIN_TOKEN=change-me`, `LLM_BASE_URL=https://integrate.api.nvidia.com/v1`, `LLM_API_KEY`(빈 값), `LLM_MODEL=meta/llama-3.3-70b-instruct`
`.gitignore`: `.env`, `node_modules/`, `.next/`, `__pycache__/`, `.venv/`, `*.pyc`

- [ ] **Step 2: git init + 첫 커밋**

Run: `git init && git add -A && git commit -m "chore: repo skeleton + docker compose postgres"`

- [ ] **Step 3: 기동 확인**

Run: `docker compose up -d` 후 `docker compose exec db pg_isready -U insight`
Expected: `accepting connections`

### Task 2: DB 마이그레이션 러너 + 초기 스키마

**Files:**
- Create: `collector/requirements.txt`, `collector/aic/__init__.py`, `collector/aic/config.py`, `collector/aic/db.py`, `collector/db/migrations/001_init.sql`, `collector/tests/conftest.py`, `collector/tests/test_migrate.py`

**Interfaces:**
- Produces:
  - `aic.config.load_config() -> Config` (pydantic BaseSettings 스타일: `database_url`, `database_url_test`, `github_token`, `admin_token`, `llm_base_url`, `llm_api_key`, `llm_model`)
  - `aic.db.connect(dsn: str) -> psycopg.Connection`
  - `aic.db.migrate(conn, migrations_dir: Path) -> list[str]` (적용된 파일명 반환, `schema_migrations` 테이블로 멱등)
- 스키마: 설계 문서 §5.1의 7개 테이블(`entries`, `appearances`, `metric_snapshots`, `raw_items`, `llm_cache`, `crawl_runs`, `config`) + 인덱스(`entries(stars desc)`, `entries(category)`, GIN on `entries(tags)`, `entries(search_tsv)` 생성 컬럼 + GIN, `pg_trgm` 확장 + `entries(canonical_name) gin_trgm_ops`)

- [ ] **Step 1: 의존성 설치** — `collector/requirements.txt` 작성 후 `python -m venv .venv; .venv\Scripts\pip install -r requirements.txt pytest` (httpx, psycopg[binary], pydantic-settings, openai, apscheduler, fastapi, uvicorn, pytest)
- [ ] **Step 2: 실패 테스트 작성**

```python
# collector/tests/test_migrate.py
def test_migrate_idempotent(test_db_conn):
    from aic.db import migrate
    applied1 = migrate(test_db_conn, MIGRATIONS_DIR)
    applied2 = migrate(test_db_conn, MIGRATIONS_DIR)
    assert "001_init.sql" in applied1
    assert applied2 == []
    rows = test_db_conn.execute("select tablename from pg_tables where schemaname='public'").fetchall()
    names = {r[0] for r in rows}
    assert {"entries","appearances","metric_snapshots","raw_items","llm_cache","crawl_runs","config"} <= names
```

- [ ] **Step 3: 실행 → FAIL 확인** (`python -m pytest tests/test_migrate.py -v` — migrate 미구현으로 실패)
- [ ] **Step 4: migrate 러너 + 001_init.sql 구현** (SQL은 설계 문서 §5.1 그대로)
- [ ] **Step 5: 실행 → PASS** (`DATABASE_URL_TEST` 대상, conftest가 테스트 DB 생성·마이그레이션·롤백 관리)
- [ ] **Step 6: Commit** — `feat: migration runner + initial schema`

### Task 3: repo URL 정규화 + 엔트리/appearance 저장

**Files:**
- Create: `collector/aic/merge.py`, `collector/aic/models.py`, `collector/aic/store.py`, `collector/tests/test_merge.py`, `collector/tests/test_store.py`

**Interfaces:**
- Produces:
  - `aic.merge.normalize_repo_url(url: str | None) -> str | None` — `https://github.com/owner/repo` 소문자 정규형 (ssh/git/.git/쿼리/트레일링 슬래시/`www.` 제거)
  - `aic.merge.entry_slug(owner: str, name: str) -> str`
  - `aic.models.RawItem` (dataclass: `source: str, external_id: str, payload: dict`)
  - `aic.store.upsert_entry(conn, item: RawItem, kind: str, repo_url: str | None, ...) -> uuid.UUID`
  - `aic.store.attach_appearance(conn, entry_id: uuid.UUID, source: str, external_id: str, url: str | None, metrics: dict) -> None`
  - `aic.store.insert_raw_item(conn, item: RawItem, ttl_days: int = 30) -> None`

- [ ] **Step 1: 실패 테스트 작성**

```python
# test_merge.py — 정규화 케이스
@pytest.mark.parametrize("raw,expected", [
    ("https://www.github.com/Owner/Repo/", "https://github.com/owner/repo"),
    ("git@github.com:owner/repo.git", "https://github.com/owner/repo"),
    ("http://github.com/owner/repo?tab=readme", "https://github.com/owner/repo"),
    ("github.com/owner/repo#readme", "https://github.com/owner/repo"),
    ("https://gitlab.com/a/b", None),  # github 아님
    (None, None), ("", None),
])
def test_normalize_repo_url(raw, expected): ...
```

```python
# test_store.py — 병합: 다른 출처가 같은 repo URL이면 같은 entry
def test_same_repo_from_two_sources_merges(test_db_conn):
    e1 = upsert_entry(conn, RawItem("github","owner/repo",{...}), kind="mcp", repo_url="https://github.com/owner/repo")
    e2 = upsert_entry(conn, RawItem("clawhub","owner-slash-repo",{...}), kind="skill", repo_url="https://www.github.com/Owner/Repo.git")
    assert e1 == e2
    # appearance는 2개
```

- [ ] **Step 2: 실행 → FAIL** / **Step 3: 구현** / **Step 4: 실행 → PASS**
- [ ] **Step 5: Commit** — `feat: repo url normalization + entry/appearance store`

### Task 4: GitHub 소스 어댑터 (검색 + README + 스타 히스토리)

**Files:**
- Create: `collector/aic/sources/base.py`, `collector/aic/sources/github_source.py`, `collector/tests/test_github_source.py`

**Interfaces:**
- Consumes: `aic.models.RawItem`, `aic.store.*`
- Produces:
  - `class GithubSource: __init__(client: httpx.Client, token: str | None, queries: list[str], max_per_query: int = 1000)`
  - `.fetch() -> list[RawItem]` (Search API, `sort=stars`, per_page=100, X-RateLimit-Remaining<5이면 중단)
  - `.fetch_readme(full_name: str) -> str | None` (raw.githubusercontent.com/{full_name}/HEAD/README.md, 404→None)
  - `.fetch_star_history(full_name: str, max_pages: int = 10) -> list[datetime]` (`Accept: application/vnd.github.star+json`의 `starred_at`)
  - 모듈 함수 `polite_get(client, url, **kw) -> httpx.Response` — 429+Retry-After 처리 공통화 (다른 어댑터도 사용)

- [ ] **Step 1: 실패 테스트 작성** — httpx `MockTransport`로: (a) 2페이지 검색 결과 수집, (b) 429→Retry-After 대기 후 재시도 성공, (c) 재차 429→빈 리스트 + 정상 반환, (d) starred_at 파싱, (e) README 404→None
- [ ] **Step 2: 실행 → FAIL** / **Step 3: 구현** / **Step 4: 실행 → PASS**
- [ ] **Step 5: Commit** — `feat: github source adapter`

### Task 5: MCP Registry + npm 어댑터

**Files:**
- Create: `collector/aic/sources/mcp_registry.py`, `collector/aic/sources/npm_source.py`, `collector/tests/test_registry_npm.py`

**Interfaces:**
- Produces:
  - `class McpRegistrySource: __init__(client, base_url="https://registry.modelcontextprotocol.io")` → `.fetch() -> list[RawItem]` (`/v0/servers?limit=100&cursor=...`, external_id=`server.name`, repo_url은 payload에서 추출)
  - `class NpmSource: __init__(client, keywords=("mcp-server","mcp"))` → `.fetch() -> list[RawItem]` (`registry.npmjs.org/-/v1/search`, payload에 `downloads.monthly` 포함, repository.git+ssh URL도 `normalize_repo_url` 통과)

- [ ] **Step 1: 실패 테스트 (MockTransport JSON fixture)** / **Step 2: FAIL** / **Step 3: 구현** / **Step 4: PASS** / **Step 5: Commit** — `feat: mcp registry + npm adapters`

### Task 6: skills.sh 폴백 + ClawHub 어댑터

**Files:**
- Create: `collector/aic/sources/skills_sh.py`, `collector/aic/sources/clawhub.py`, `collector/tests/test_skills_sources.py`, `collector/tests/fixtures/skills_sh_leaderboard.html`

**Interfaces:**
- Produces:
  - `class SkillsShSource: __init__(client, mode: str)` — `mode="html"`(폴백): `https://skills.sh` 리더보드 SSR 파싱(순위·이름·owner/repo·설치수) → RawItem(source="skills_sh"). `mode="oidc"`는 `NotImplementedError` 유지(확장점)
  - `class ClawhubSource: __init__(client, base_url="https://clawhub.ai")` → `.fetch() -> list[RawItem]` (`/api/v1/skills?sort=downloads&limit=100` + cursor, external_id=`ownerHandle/slug`)
  - 둘 다 `polite_get` 사용

- [ ] **Step 1: 실패 테스트** — fixture HTML 파싱(3행 검증), ClawHub MockTransport 2페이지 cursor 순회
- [ ] **Step 2: FAIL** / **Step 3: 구현** / **Step 4: PASS** / **Step 5: Commit** — `feat: skills.sh fallback + clawhub adapters`

### Task 7: 스냅샷·급상승 delta·콜드스타트 백필

**Files:**
- Create: `collector/aic/snapshots.py`, `collector/tests/test_snapshots.py`

**Interfaces:**
- Consumes: `GithubSource.fetch_star_history`, `aic.store.*`
- Produces:
  - `capture_snapshots(conn, rows: Iterable[tuple[uuid, str, dict]]) -> None` (metric_snapshots insert)
  - `recompute_deltas(conn, now: datetime) -> int` — 각 entry의 최신 스냅샷 대비 24h/7d 이전 스냅샷 차이를 `entries.stars_delta_24h/7d`에 기록 (이전 시점 스냅샷 없으면 가용 최선 구간), 업데이트 행 수 반환
  - `backfill_star_history(conn, gh: GithubSource, limit: int = 500) -> int` — stars desc 상위 limit개 entry의 starred_at을 7일 경계로 집계해 과거 시점 스냅샷을 합성 삽입, 처리 건수 반환

- [ ] **Step 1: 실패 테스트** — (a) t-24h, t-7d 스냅샷 심어 delta 계산 검증, (b) 스냅샷 1개뿐인 entry는 delta NULL 유지, (c) `fetch_star_history`가 MockTransport로 [어제 3개, 5일전 10개]를 주면 합성 스냅샷 2개 생성
- [ ] **Step 2: FAIL** / **Step 3: 구현** / **Step 4: PASS** / **Step 5: Commit** — `feat: snapshots + trending deltas + star history backfill`

### Task 8: LLM 클라이언트 + provider 프리셋

**Files:**
- Create: `collector/aic/enrich/__init__.py`, `collector/aic/enrich/llm_client.py`, `collector/tests/test_llm_client.py`

**Interfaces:**
- Produces:
  - `PRESETS: dict[str, str]` = `{"nvidia": "https://integrate.api.nvidia.com/v1", "openrouter": "https://openrouter.ai/api/v1"}` (+base_url이 presets와 매칭되면 provider명 반환하는 `detect_provider(base_url) -> str | None`)
  - `@dataclass LlmSettings: base_url, api_key, model`
  - `get_settings(conn) -> LlmSettings` — `config` 테이블 키 `llm` > `.env` 순
  - `save_settings(conn, s: LlmSettings) -> None`
  - `list_models(s: LlmSettings, client: httpx.Client) -> list[str]` — `GET {base}/models`, 실패 시 `[]`
  - `chat_json(s: LlmSettings, system: str, user: str) -> dict` — openai SDK(base_url 주입), 응답에서 첫 JSON 객체 추출, 실패 시 `LlmError`

- [ ] **Step 1: 실패 테스트** — (a) 프리셋 감지, (b) `/models` 파싱 + 실패 시 빈 리스트, (c) chat_json이 코드펜스 포함 응답에서도 JSON 추출, (d) config 테이블이 env보다 우선
- [ ] **Step 2: FAIL** / **Step 3: 구현** / **Step 4: PASS** / **Step 5: Commit** — `feat: llm client + provider presets`

### Task 9: 요약·설치법·태그 파이프라인

**Files:**
- Create: `collector/aic/enrich/summarizer.py`, `collector/tests/test_summarizer.py`

**Interfaces:**
- Consumes: `chat_json`, `get_settings`, `aic.store.*`
- Produces:
  - `@dataclass SummaryResult: summary_ko: str, usage_ko: str, install_commands: list[dict], tags: list[str], category: str`
  - `CATEGORY_TAXONOMY: list[str]` = 설계 문서 §5.4 10개
  - `select_pending(conn, limit: int = 100) -> list[dict]` — `(stars>=50 OR installs>=100) AND (summary_ko IS NULL OR readme_hash 변경)` 상위, README 미보유면 fetch 후 저장
  - `build_prompt(entry: dict, readme: str | None) -> tuple[str, str]` (system, user) — README 20KB 절단 포함
  - `apply_summary(conn, entry_id: uuid.UUID, result: SummaryResult, readme_hash: str) -> None`
  - `run_enrichment(conn, settings: LlmSettings, limit: int = 100) -> dict` — llm_cache(`input_hash`=sha256(system+user+model)) hit면 LLM 호출 스킵; LLM/JSON 실패 시 해당 엔트리 스킵 후 계속, 반환 `{"summarized": n, "cache_hits": n, "failed": n}`

- [ ] **Step 1: 실패 테스트** — (a) fake LLM 클라이언트로 apply 검증, (b) 동일 입력 2회차에 cache hit(LLM 호출 1회만), (c) LLM이 깨진 JSON → failed 카운트 + 엔트리는 summary_ko NULL로 공개 가능 상태 유지, (d) README 1MB → 20KB 절단, (e) README None → 빈 본문 프롬프트로 진행, (f) category가 taxonomy 밖이면 "기타"로 보정
- [ ] **Step 2: FAIL** / **Step 3: 구현** / **Step 4: PASS** / **Step 5: Commit** — `feat: summarization pipeline with cache`

### Task 10: 스케줄러 + control API + main 엔트리포인트

**Files:**
- Create: `collector/aic/control_api.py`, `collector/aic/scheduler.py`, `collector/aic/main.py`, `collector/tests/test_control_api.py`

**Interfaces:**
- Consumes: 모든 어댑터, snapshots, summarizer
- Produces:
  - `create_app(conn_factory) -> FastAPI` — `POST /run/{source}` (헤더 `X-Admin-Token` 검사; source ∈ {github, skills_sh, clawhub, mcp_registry, npm, snapshots, enrich, backfill}), `GET /status` (crawl_runs 최근 20개), `GET /llm/models` (admin), 응답은 `{"ok": true, "stats": {...}}`
  - `run_job(conn, source: str) -> dict` — 각 소스 fetch→store→(github이면 snapshot)→crawl_runs 기록의 공통 흐름
  - `delete_expired_raw_items(conn) -> int` — `expires_at < now()`인 raw_items 삭제, 삭제 행 수 반환
  - `build_scheduler(conn_factory) -> APScheduler` — 기본 스케줄: github/snapshots 6h, skills_sh/clawhub 12h, mcp_registry/npm 24h, recompute_deltas 1h, raw 정리 1d
  - `main.py`: migrate → 스케줄러 시작 → uvicorn(127.0.0.1:8111) control API

- [ ] **Step 1: 실패 테스트 (fastapi TestClient)** — (a) 토큰 없이 POST /run/github → 401, (b) 올바른 토큰 + monkeypatch된 run_job → 200 + stats, (c) GET /status에 crawl_runs 반영, (d) 미지 source → 400
- [ ] **Step 2: FAIL** / **Step 3: 구현** / **Step 4: PASS** / **Step 5: Commit** — `feat: scheduler + control api`

### Task 11: Next.js 골격 + DB 읽기/쓰기 레이어

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/next.config.ts`, `web/src/db/schema.ts` (Drizzle), `web/src/db/queries.ts`, `web/tests/queries.test.ts`, `web/vitest.config.ts`

**Interfaces:**
- Consumes: Task 2 스키마 (Drizzle 스키마가 동일 테이블 정의)
- Produces:
  - `type Ranking = "stars" | "trending" | "new" | "installs"`
  - `rankingEntries(kind: Ranking, limit = 50) -> Promise<Entry[]>` — stars: `stars desc where pushed_at>now-180d`; trending: `stars_delta_7d desc nulls last, stars desc`; new: `github_created_at>now-90d order by stars_delta_7d desc nulls last`; installs: `installs desc nulls last`
  - `searchEntries({q, category, kind, sort, limit, offset}) -> Promise<{items: Entry[], total: number}>` — `websearch_to_tsquery('simple', q)` + `ILIKE '%q%' OR canonical_name % q`(pg_trgm) OR 태그 배열 포함
  - `getEntryBySlug(slug) -> Promise<EntryDetail | null>` (appearances 포함 + 최근 14일 스냅샷 시계열)
  - `getCrawlRuns(limit)`, `getConfig/setConfig(key, value)` (admin용 최소 쓰기)

- [ ] **Step 1: 의존성 설치** — `web`에서 `npm install next@15 react react-dom drizzle-orm pg && npm install -D typescript vitest @types/pg @types/node tsx`
- [ ] **Step 2: 실패 테스트** — test DB에 seed 3행 삽입 후: (a) ranking 4종 정렬 순서 검증(trending은 delta NULL이 마지막), (b) "노션" 검색이 name "Notion MCP" 엔트리 히트(trgm), (c) category 필터, (d) getEntryBySlug가 appearances 2개 포함
- [ ] **Step 3: FAIL** / **Step 4: 구현** / **Step 5: PASS** / **Step 6: Commit** — `feat: web db layer + queries`

### Task 12: 포털 페이지 — 랭킹·검색·상세

**Files:**
- Create: `web/src/app/layout.tsx`, `web/src/app/page.tsx`, `web/src/app/search/page.tsx`, `web/src/app/entry/[slug]/page.tsx`, `web/src/components/EntryCard.tsx`, `web/src/components/Sparkline.tsx`, `web/src/components/InstallCommands.tsx`, `web/src/app/sitemap.ts`

**Interfaces:**
- Consumes: Task 11 queries 전부
- Produces: 렌더링된 3페이지 + `Sparkline(points: number[]): JSX`(의존성 없는 SVG), `InstallCommands(cmds: {target, cmd}[]): JSX`(복사 버튼)

- [ ] **Step 1: 페이지 구현** — `/`는 탭(전체 스타/급상승/신규 급상승/설치수)+검색창+EntryCard 목록, `/search`는 q·category·kind 필터(서버 컴포넌트, searchParams), `/entry/[slug]`는 한국어 요약·사용법·설치법(타깃별 복사 버튼)·출처 링크 목록·Sparkline·보안 감사(있으면). 요약이 NULL이면 "요약 준비 중" 배지 + 원문 링크는 항상 표시
- [ ] **Step 2: 빌드·렌더 확인** — `npm run build` 성공, `npm run dev` 후 `curl -s localhost:3000 | grep ai_insight`, 빈 DB에서도 3페이지 모두 200
- [ ] **Step 3: Commit** — `feat: portal pages`

### Task 13: /admin 대시보드 + LLM 설정 UI

**Files:**
- Create: `web/src/app/admin/page.tsx`, `web/src/app/admin/settings/page.tsx`, `web/src/app/api/admin/run/route.ts`, `web/src/app/api/admin/models/route.ts`, `web/src/app/api/admin/config/route.ts`, `web/src/components/AdminTokenGate.tsx`

**Interfaces:**
- Consumes: Task 10 control API (`POST /run/{source}`, `GET /status`, `GET /llm/models`), Task 11 `getConfig/setConfig`
- Produces: admin 2페이지 + 3 API 라우트. API 라우트는 `X-Admin-Token`(요청 헤더)을 collector로/DB로 전달. `models` 라우트는 설정된 base_url+key로 collector의 `/llm/models`를 프록시

- [ ] **Step 1: 구현** — admin 홈: crawl_runs 테이블(상태·소스·건수·시각) + 소스별 "지금 수집" 버튼(진행 중 disabled). settings: provider 프리셋 셀렉트(nvidia/openrouter/직접입력) → 모델 드롭다운(list_models 성공 시) 또는 텍스트 입력(실패 시) → 저장(setConfig("llm"))
- [ ] **Step 2: 확인** — 잘못된 토큰으로 POST → 401, 올바른 토큰 + collector 미기동 → 우아한 에러 배지. `npm run build` 성공
- [ ] **Step 3: Commit** — `feat: admin dashboard + llm settings`

### Task 14: 초기 백필 실행 + 전체 스모크

**Files:**
- Create: `collector/scripts/initial_backfill.py`, `docs/runbook.md`

**Interfaces:**
- Consumes: 전부. `python scripts/initial_backfill.py` = github fetch → github README 보강 → snapshots 캡처 → backfill_star_history(500) → recompute_deltas → enrich(limit 100, 키 없으면 자동 스킵) → skills_sh/clawhub/mcp_registry/npm fetch

- [ ] **Step 1: runbook 작성** — 기동 순서(docker compose up → collector → web), .env 채우기, 문제 해결(429·포트 충돌)
- [ ] **Step 2: 실행** — `docker compose up -d` → backfill 실행 → (사용자 키가 있으면) enrich → 웹에서 랭킹 4개 탭·검색·상세·admin 수동 트리거 확인
- [ ] **Step 3: 커밋** — `feat: initial backfill script + runbook`
