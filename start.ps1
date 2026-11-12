# ai_insight 전체 기동: DB + 수집기 + 포털 (한 줄: .\start.ps1)
$root = $PSScriptRoot
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host "[1/3] PostgreSQL (docker compose)" -ForegroundColor Cyan

# Docker Desktop 실행 확인 — 꺼져 있으면 자동 실행 후 대기
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Docker Desktop이 꺼져 있습니다 — 자동 실행 시도..." -ForegroundColor Yellow
    $dd = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dd) {
        Start-Process -FilePath $dd
    } else {
        Write-Host "  [오류] Docker Desktop을 찾을 수 없습니다. 직접 실행한 뒤 다시 .\start.ps1" -ForegroundColor Red
        exit 1
    }
    $waited = 0
    do {
        Start-Sleep -Seconds 5
        $waited += 5
        Write-Host "  Docker 시작 대기... ${waited}초" -ForegroundColor DarkGray
        docker info 2>$null | Out-Null
    } while ($LASTEXITCODE -ne 0 -and $waited -lt 120)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [오류] Docker 시작 실패 (2분 초과) — Docker Desktop을 실행한 뒤 다시 .\start.ps1" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Docker 시작됨" -ForegroundColor Green
}

# DB 컨테이너 기동 + healthy까지 대기 (--wait: 헬스체크 통과 대기)
docker compose -f "$root\docker-compose.yml" up -d --wait
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [경고] DB healthy 대기 시간 초과 — 일단 진행합니다" -ForegroundColor Yellow
}

Write-Host "[2/3] 수집기 (aic.main) — 로그: logs\collector.log" -ForegroundColor Cyan
# cmd 래퍼 + >> : 재기동해도 로그가 append됨. python -u : 버퍼링 없이 실시간 기록
Start-Process -FilePath "cmd.exe" `
  -ArgumentList "/c", "cd /d $root\collector && .venv\Scripts\python.exe -u -m aic.main >> $logDir\collector.log 2>&1" `
  -WindowStyle Minimized

Write-Host "[3/3] 포털 (next dev) — 로그: logs\web-dev.log" -ForegroundColor Cyan
Start-Process -FilePath "cmd.exe" `
  -ArgumentList "/c", "cd /d $root\web && npm run dev >> $logDir\web-dev.log 2>&1" `
  -WindowStyle Minimized

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "기동 완료 (각 창은 최소화되어 실행 중):" -ForegroundColor Green
Write-Host "  포털               http://localhost:3001"
Write-Host "  수집기 control API http://127.0.0.1:8111"
Write-Host "  관리 화면          http://localhost:3001/admin"
Write-Host ""
Write-Host "사이트 갱신 순서 (관리 화면 버튼):" -ForegroundColor Yellow
Write-Host "  GitHub 수집 -> LLM 요약 -> 배포   (배포까지 눌러야 공개 사이트에 반영)"
Write-Host ""
Write-Host "로그 확인:" -ForegroundColor Yellow
Write-Host "  수집기  Get-Content $logDir\collector.log -Tail 50 -Wait"
Write-Host "  포털    Get-Content $logDir\web-dev.log -Tail 50 -Wait"
Write-Host ""
Write-Host "중지: docker compose stop + minimized 창 닫기"