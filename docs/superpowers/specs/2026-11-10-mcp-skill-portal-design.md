# MCP·Skill 포털 설계 문서 (코드명: ai_insight)

- 작성일: 2026-11-10
- 상태: 초안 (사용자 승인 대기)
- 프로젝트 위치: `D:\ai_insight`

---

## 1. 의도 (Intent)

AI 에이전트 생태계의 핵심 부품 — **MCP 서버**와 **에이전트 스킬(skill)** — 이 GitHub, skills.sh, ClawHub, GeekNews 등 여러 곳에 흩어져 폭발적으로 늘고 있다. 사용자는 이것을 한곳에서 모아 **포털**로 소비하고 싶어 한다:

- 랭킹(원래 유명한 것 + 스타 급상승)으로 "지금 주목받는 부품"을 파악
- 각 항목의 **한국어 요약 + 간단 설치법 + 사용법**을 원문 출처 링크와 함께 제공
- 태그·카테고리 기반 검색

운영자(사용자)는 포털화에 집중하고, 콘텐츠는 수집·정제 파이프라인이 채운다. 모든 엔트리는 원문 출처를 반드시 표기한다(포털은 요약과 안내만, 원문 미러링은 하지 않음).

## 2. 목표 / 비목표 / 안티목표

### 목표 (MVP)
- **수집 소스 (전부 공개 API)**:
  1. GitHub Search API — `topic:mcp-server`(4.2만), `topic:claude-skills`(1.5만), 기타 설정 가능한 쿼리 목록. star 정렬 + 전체 메타데이터(stars, topics, license, pushed_at 등)
  2. skills.sh (Vercel) — 리더보드(중복 제거 설치수), trending/hot, 검색, 스킬 상세(SKILL.md 전문), 보안 감사
  3. ClawHub — 공개 REST API (문서상 서드파티 디렉터리 이용 명시 허용, 조건: 캐시·원본 링크 표기). `/api/v1/skills?sort=downloads|trending|stars`, 검색, 상세(readme 200KiB)
  4. 공식 MCP Registry — `registry.modelcontextprotocol.io/v0/servers` (검색·커서). 인기 지표는 없고 등록 여부/원격 URL/버전 등 보완 정보
  5. npm registry — `mcp-server` 계열 패키지 검색, 월 다운로드수 지표
- **엔티티 통합**: 같은 프로젝트의 여러 출처 등장(appearance)을 GitHub repo URL 정규화 기준으로 하나의 엔트리로 병합
- **랭킹**:
  - 전체 스타 랭킹 (최근 180일 내 푸시된 리포 기준)
  - **스타 급상승**: metric snapshot의 24h/7d 증가분 기반 스코어
  - 신규 급상승: GitHub 생성 90일 이내 + 7일 증가분 순
  - 설치수 랭킹: skills.sh installs / ClawHub downloads / npm 월 다운로드
- **LLM 정제**: README/SKILL.md → 한국어 요약(3~5문장) + 사용법 요약 + **설치 커맨드 추출**(`claude mcp add ...`, `npx skills add owner/repo`, `openclaw skills install @owner/slug` 등 타깃별 정리) + 태그/카테고리. OpenAI 호환 엔드포인트(기본 NVIDIA NIM) 사용.
- **LLM 설정 유연성**: 엔드포인트·모델·키를 설정에서 변경 가능. 알려진 provider(NVIDIA NIM, OpenRouter 등) 프리셋을 고르면 `GET /v1/models`로 모델 목록을 가져와 드롭다운 제공. 목록을 못 가져오는 커스텀 엔드포인트는 직접 입력 폴백.
- **웹 포털 (Next.js)**: 랭킹 탭, 검색(이름/요약/태그, 카테고리 필터, kind 필터), 상세 페이지(요약·설치법·출처 링크 목록·스타 추이), 수집 현황 관리 대시보드
- **수집기 (Python)**: 스케줄 자동 실행 + 대시보드 수동 트리거. 429/Retry-After 준수, 소스별 rate limit 가드.

### 비목표 (MVP에서 안 함)
- 사용자 계정·로그인·댓글 등 커뮤니티 기능
- GeekNews 수집 (2단계 — 공식 RSS + SSR HTML이나 매너 슬로팅 설계 필요)
- Reddit / Hacker News / X 수집
- 영어 UI (한국어 단일)
- 시맨틱/벡터 검색 (2단계 — pgvector)
- 클라우드 배포 자동화 (로컬 우선)

### 안티목표 (절대 금지)
- 원문 전체 무단 미러링 (요약 + 출처 링크가 원칙)
- 대상 사이트에 부하 (레이트리밋·캐시 지시 위반, 특히 ClawHub 문서의 조건 위반)
- API 키를 코드/커밋에 노출 (전부 `.env`로, 사용자가 직접 채움)

## 3. 제약

- Windows 로컬 개발. Node 24.22 / npm 11.19 / Python 3.12 확인됨.
- **PostgreSQL은 Docker Compose로 구동 (사용자 확정)** — 마일스톤 1의 첫 작업. M1에 "Docker Desktop 동작 확인" 단계 포함. 호스트 포트 5434 (5433은 기존 컨테이너 점유)
- GitHub 무인증 60 req/h, 검색 10 req/min → `.env`의 `GITHUB_TOKEN`으로 5,000 req/h 확보 (사용자가 키 발급·삽입)
- skills.sh API는 Vercel OIDC 인증 필요(무인증 401 확인). **결정: 폴백 모드 우선 구현**(SSR 리더보드 파싱 + GitHub raw로 상세 대체), OIDC 어댑터는 추후 플러그인 구조로 추가
- LLM 비용은 사용자의 NIM 키로 부담 → 요약은 `llm_cache`(입력 해시 기반)로 중복 호출 방지, README는 20KB 절단
- **수집 규모 상한 (사용자 비용 보호, 전부 config로 조절)**: GitHub 쿼리당 상위 1,000개, 스냅샷 tracked 상한 3,000, LLM 요약 대상은 스타≥50 또는 설치≥100인 엔트리, 실행당 요약 100건
- psql 접근은 전부 `DATABASE_URL` 환경변수 사용
- **보안 기본값**: 웹은 localhost 바인딩. `/admin`과 collector control API는 `ADMIN_TOKEN` 환경변수 게이트 (공개 노출 대비 1차 방어선)

## 4. 접근 방식 (Approaches)

### Approach A — Next.js 포털 + Python 수집기 + PostgreSQL 공유 (선택됨)
- 웹은 Next.js (App Router, SSR) — 검색 노출과 체감 속도, 사용자 선호(이전 프로젝트에서 3번으로 선택)와 일치
- 수집·LLM 배치는 Python 별도 프로세스 — httpx/openai SDK/스케줄러 생태계가 성숙, 장시간 배치에 적합
- 둘은 PostgreSQL 스키마로만 소통 → 결합도 최소, 수집기 교체 가능
- **트레이드오프**: 두 런타임(패키지 관리×2)을 관리해야 함

### Approach B — Next.js 풀스택 단독 (기각)
- 수집 배치가 서버리스/타임아웃 모델과 부적합하고, 급상승 스냅샷 같은 상태 작업이 Next.js API route에 어울리지 않음

### Approach C — Django 풀스택 단독 (기각)
- 어드민은 편하나 공개 포털 UX/SEO 관점에서 Next.js가 우위, 사용자가 이미 Next.js 선호

## 5. 시스템 구성 (선택된 설계)

```
D:\ai_insight\
├─ web\        # Next.js (포털 + 관리 대시보드)
├─ collector\  # Python (수집·정제·LLM 파이프라인)
├─ docs\       # 설계·결정 기록
├─ .env        # 키·설정 (커밋 금지), .env.example 제공
└─ docker-compose.yml (선택: PostgreSQL 편의 설치용)
```

### 5.1 PostgreSQL 스키마 (핵심 테이블)

```sql
-- canonical 엔트리 (MCP 서버·스킬·플러그인 공통)
entries (
  id uuid pk,
  kind text check (kind in ('mcp','skill','plugin','library')),
  slug text unique not null,          -- 규칙: "{owner}/{name}" (github 기준)
  canonical_name text not null,
  summary_ko text,                    -- LLM 한국어 요약
  usage_ko text,                      -- LLM 한국어 사용법 요약
  install_commands jsonb,             -- [{target:"claude-code", cmd:"claude mcp add ..."}, ...]
  tags text[],                        -- LLM 생성 자유 태그 (한국어+영어)
  category text,                      -- 고정 택소노미 (아래 5.4)
  repo_url text, homepage_url text, license text,
  stars int default 0,
  stars_delta_24h int, stars_delta_7d int,   -- 스냅샷 재계산 job이 갱신
  installs int,                       -- 출처 중 최댓값
  npm_downloads_monthly int,
  github_created_at timestamptz, github_pushed_at timestamptz,
  readme_hash text,                   -- 요약 캐시 무효화용
  entry_status text default 'active', -- active|archived|hidden
  first_seen_at timestamptz, last_crawled_at timestamptz
)

-- 출처별 등장 기록 (원문 출처 표기의 근거)
appearances (
  id uuid pk, entry_id fk entries,
  source text,            -- github|skills_sh|clawhub|mcp_registry|npm|geeknews
  external_id text, url text, metrics jsonb,
  first_seen_at, last_seen_at,
  unique (source, external_id)
)

-- 급상승 계산의 원료: 주기적 지표 스냅샷
metric_snapshots (id, entry_id fk, source text, captured_at timestamptz, metrics jsonb)

-- 원문 응답 캐시 (TTL 기본 30일, 설정 가능 — 정리 job이 주기 삭제)
raw_items (id, source, external_id, payload jsonb, fetched_at, expires_at)

-- LLM 결과 캐시 (입력 해시 + 모델 기준)
llm_cache (input_hash text pk, model text, kind text, output jsonb, created_at)

-- 수집 실행 이력 (대시보드 현황)
crawl_runs (id, source, kind, status, started_at, finished_at, stats jsonb, error text)

-- 런타임 설정 (LLM 엔드포인트/모델, 수집 쿼리 목록, 스케줄 등)
config (key text pk, value jsonb, updated_at)
```

인덱스: `entries(stars desc)`, `entries(category)`, `entries(tags gin)`, `entries` 검색용 tsvector 생성 컬럼 + gin. 한국어 전문검색은 MVP에서 `simple` 설정 tsquery + `pg_trgm` 유사도 보조로 충분히 커버(빌더가 조정 가능).

### 5.2 수집기 (Python, `collector/`)

- **소스 어댑터** 인터페이스: `fetch() -> raw_items` / `normalize() -> appearances + entries upsert`
  - `github`: 쿼리 목록(config)으로 검색, per_page=100 페이지네이션, star 정렬. README는 contents API 또는 raw.githubusercontent.com
  - `skills_sh`: auth 모드 2개 — `vercel_oidc`(토큰 있으면) / `anonymous_html` 폴백(리더보드만). 상세 파일 없으면 repo README로 대체
  - `clawhub`: 공개 API, 429/Retry-After 준수, canonical 링크 표기
  - `mcp_registry`: 서버 목록 → repo_url 매칭으로 entries에 appearance 추가
  - `npm`: `mcp-server`/`mcp` 키워드 검색, 월 다운로드 수집
- **병합 규칙**: repo URL 정규화(프로토콜/쿼리 제거, github.com/owner/repo 소문자) → 동일 엔트리 판정. skills.sh/ClawHub의 GitHub 출처 정보(installUrl, provenance)를 매칭에 활용
- **스냅샷 job**: tracked entries(상한 3,000)의 stars/installs를 주기 저장, 이후 `stars_delta_24h/7d` 재계산
- **콜드스타트 백필**: 신규 트랙킹 상위 500개 엔트리에 대해 GitHub stargazers API(`Accept: application/vnd.github.star+json`, `starred_at` 포함)로 최근 7일 스타 히스토리를 복원 → 급상승 탭이 1일차부터 유효. 페이지 상한 리포당 10페이지
- **LLM enrichment 큐**: readme_hash가 바뀌었거나 요약이 없는 entries만 처리 → 요약·사용법·설치법·태그 생성 → `llm_cache` 저장/재사용
- **스케줄(기본값, config로 변경 가능)**: GitHub 검색 6h, 스냅샷 6h, skills.sh/ClawHub 12h, MCP registry 24h, npm 24h, 스냅샷 delta 재계산 1h, raw 캐시 정리 1d
- **수동 트리거**: collector가 작은 control API(FastAPI)를 노출 — 대시보드의 "지금 수집" 버튼이 호출
- politeness: 소스별 토큰버킷, 429 시 Retry-After 대기, 실행 상한(실행당 최대 요청 수) config

### 5.3 LLM 파이프라인

- OpenAI 호환 클라이언트 하나로 NIM·OpenRouter·커스텀 전부 커버 (base_url 교체)
- 프리셋 provider: `nvidia`(`https://integrate.api.nvidia.com/v1`), `openrouter`(`https://openrouter.ai/api/v1`) → `GET /v1/models`로 드롭다운
- 프롬프트 1회 호출로 JSON 출력: `{summary_ko, usage_ko, install_commands[], tags[], category}`
- 실패 시 재시도 2회 → 실패 항목은 `entry_status` 그대로 두고 요약 없이 공개(원문 링크는 항상 있음)

### 5.4 카테고리 택소노미 (초안)

`검색·브라우저 / 파일·문서 / 데이터베이스 / 개발자 도구 / 이미지·영상 / 메모리·컨텍스트 / 에이전트 프레임워크 / 클라우드·인프라 / 생산성 / 기타`

- 1차: GitHub topics → 카테고리 규칙 매핑(결정적, 비용 0)
- 2차: 매핑 실패 시에만 LLM 분류

### 5.5 웹 포털 (Next.js, `web/`)

- `/` — 랭킹 탭: [전체 스타 | 스타 급상승(24h/7d) | 신규 급상승 | 설치수] + 검색창
- `/entry/[slug]` — 한국어 요약, 사용법, 타깃별 설치 커맨드(복사 버튼), 출처 링크 목록(원문 출처), 스타 추이 미니 차트, 보안 감사 요약(있으면)
- `/search?q=&category=&kind=&sort=` — 태그·카테고리·전문검색
- `/admin` — 크롬 런 이력/건수/LLM 큐 상태, "지금 수집" 버튼, LLM 설정(프로바이더 프리셋 → 모델 드롭다운 / 직접 입력), 수집 쿼리 관리
- 데이터 접근: Next.js가 PostgreSQL 직접 조회 (Drizzle ORM — 가볍고 SQL 가까움. 빌더가 대안 제시 가능하나 이유 필요)
- SEO: SSR + 메타태그, sitemap

## 6. 마일스톤

1. **M1 인프라**: PostgreSQL 설치(방식 합의), 스키마 마이그레이션, 저장소 골격, `.env.example`
2. **M2 GitHub 수집기**: 검색+스냅샷+병합까지 동작, CLI로 수동 실행 확인
3. **M3 LLM 정제**: NIM 설정, 요약·설치법·태그, 캐시
4. **M4 나머지 소스**: skills.sh / ClawHub / MCP registry / npm 어댑터
5. **M5 포털**: 랭킹·검색·상세 페이지
6. **M6 관리 대시보드**: 현황, 수동 트리거, LLM 설정 UI
7. **M7 (2단계)**: GeekNews RSS 수집, 폴리싱

## 7. 결정된 사항 (구 결정 대기 항목)

1. 포털 이름 — 미정 → UI 작업명 `ai_insight` 사용, config로 교체 가능
2. PostgreSQL 설치 — **Docker Compose (사용자 확정)**
3. skills.sh 인증 — **폴백 모드 우선**, OIDC는 어댑터 확장으로 보류 (Vercel 계정 생기면 전환)
4. 카테고리 택소노미 — 5.4 초안으로 진행 (config에 있어 수정 가능)
5. GitHub 토큰 — 사용자가 `.env`에 삽입, 무인증 저속 모드로도 수집기는 동작

## 8. 빌더에게 남긴 것

- tsvector/검색 쿼리 세부 튜닝, 스타 급상승 스코어 공식의 미세 조정 (초안: `score = stars_delta_7d`, 동점 시 stars desc — 2주 데이터 쌓인 뒤 재조정)
- 차트 라이브러리 선택 (경량 SVG 직접 렌더 or Recharts)
- 마이그레이션 도구 상세 (Drizzle kit 권장)
- 에러/재시도 정책의 세부 파라미터
