# ai_insight 전체 기동: DB + 수집기 + 포털 (한 줄: .\start.ps1)
$root = $PSScriptRoot
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host "[1/3] PostgreSQL (docker compose)" -ForegroundColor Cyan
docker compose -f "$root\docker-compose.yml" up -d

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
Write-Host "  포털              http://localhost:3001"
Write-Host "  수집기 control API http://127.0.0.1:8111"
Write-Host "  관리 화면          http://localhost:3001/admin"
Write-Host ""
Write-Host "로그 확인:" -ForegroundColor Yellow
Write-Host "  수집기  Get-Content $logDir\collector.log -Tail 50 -Wait"
Write-Host "  포털    Get-Content $logDir\web-dev.log -Tail 50 -Wait"
Write-Host ""
Write-Host "중지: docker compose stop + minimized 창 닫기"
