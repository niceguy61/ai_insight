# Runbook — ai_insight 운영 안내

## 기동 순서

```powershell
# 0. 저장소 루트에서
cd D:\ai_insight

# 1. PostgreSQL 기동 (포트 5434)
docker compose up -d

# 2. 환경설정 — .env를 만들고 키를 채운다 (최초 1회)
copy .env.example .env
#   GITHUB_TOKEN : https://github.com/settings/tokens (read-only public이면 충분)
#   LLM_API_KEY  : build.nvidia.com 또는 openrouter.ai 키
#   ADMIN_TOKEN  : /admin 접근용 임의 문자열

# 3. (최초 1회) 초기 데이터 채우기 — 몇 분 소요
cd collector
python -m venv .venv                 # 최초 1회
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -r requirements.txt --extra-index-url 없이 이미 됨
.venv\Scripts\python scripts\initial_backfill.py

# 4. 수집기 상시 구동 (스케줄러 + control API)
.venv\Scripts\python -m aic.main     # 127.0.0.1:8111

# 5. 포털 (다른 터미널)
cd ..\web
npm install                          # 최초 1회
npm run dev                          # http://localhost:3000
```

## 관리 화면

- `http://localhost:3000/admin` — 수집 현황, 소스별 "지금 수집" 버튼
- `http://localhost:3000/admin/settings` — LLM 엔드포인트·모델·키 설정
  (NVIDIA NIM / OpenRouter 프리셋은 모델 드롭다운 자동 로딩, 그 외는 직접 입력)
- 접속 시 `.env`의 `ADMIN_TOKEN` 입력 (브라우저 localStorage에만 저장)

## 수집 주기 (기본값)

| 소스 | 주기 |
|---|---|
| GitHub 검색 + 스냅샷 | 6시간 |
| skills.sh / ClawHub | 12시간 |
| MCP Registry / npm | 24시간 |
| 급상승 delta 재계산 | 1시간 |
| raw 캐시 정리 | 24시간 |

## 문제 해결

- **429 (rate limit)**: 각 어댑터는 Retry-After를 지키고, 지속 429 시 해당 실행을 정상 종료합니다.
  GitHub은 `.env`에 `GITHUB_TOKEN`을 넣으면 5,000 req/h가 확보됩니다.
- **포트 충돌**: PostgreSQL은 5434를 씁니다 (5433은 본 기계의 다른 컨테이너 점유).
  `docker-compose.yml`과 `.env`의 `DATABASE_URL`을 함께 바꾸세요.
- **수집기 연결 오류 (502)**: `/admin`에서 "지금 수집"이 502면 수집기(`aic.main`)가 꺼져 있는 것입니다.
- **모델 드롭다운이 비어 있음**: 엔드포인트의 `/models`가 실패한 것 — 모델명을 직접 입력하면 됩니다.
- **급상승 탭이 비어 있음**: 스냅샷이 이틀 이상 쌓여야 7일 delta가 정확해집니다.
  초기 백필(`initial_backfill.py`)이 상위 500개의 스타 히스토리를 복원하므로 1일차부터 동작합니다.

## 테스트

```powershell
# Python 수집기
cd collector; .venv\Scripts\python -m pytest tests\ -q

# Next.js 웹 (WSL이 아닌 Windows 셸에서)
cd web; npx vitest run
```
