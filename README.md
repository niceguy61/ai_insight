# ai_insight — MCP·Skill 포털

AI 에이전트 생태계의 MCP 서버와 에이전트 스킬을 수집·정제·요약해서 랭킹과 검색으로 보여주는 포털.

- 설계 문서: `docs/superpowers/specs/2026-11-10-mcp-skill-portal-design.md`
- 구현 계획: `docs/superpowers/plans/2026-11-10-mcp-skill-portal.md`

## 구성

| 디렉터리 | 역할 |
|---|---|
| `collector/` | Python 수집기 — 소스 어댑터(GitHub/skills.sh/ClawHub/MCP Registry/npm), 스냅샷, LLM 요약, 스케줄러, control API |
| `web/` | Next.js 포털 — 랭킹·검색·상세 + `/admin` |
| `docker-compose.yml` | PostgreSQL 17 (호스트 포트 5434) |

## 빠른 시작

**한 줄 기동 (권장):**

```powershell
.\start.ps1   # DB + 수집기 + 포털 전부 기동
```

**수동으로 각각 띄울 때:**

```powershell
# 1. DB 기동
docker compose up -d

# 2. 환경설정 (.env 를 만들고 키를 채운다)
copy .env.example .env

# 3. 수집기 — 주의: python 이 아니라 .venv 의 python 을 쓴다
cd collector
.venv\Scripts\python -m aic.main    # 127.0.0.1:8111

# 4. 포털 (다른 터미널)
cd ..\web
npm install                         # 최초 1회
npm run dev                         # http://localhost:3000
```

