# ai_insight 전체 기동: DB + 수집기 + 포털 (한 줄: .\start.ps1)
$root = $PSScriptRoot

Write-Host "[1/3] PostgreSQL (docker compose)" -ForegroundColor Cyan
docker compose -f "$root\docker-compose.yml" up -d

Write-Host "[2/3] 수집기 (aic.main)" -ForegroundColor Cyan
Start-Process -FilePath "$root\collector\.venv\Scripts\python.exe" `
  -ArgumentList "-m", "aic.main" `
  -WorkingDirectory "$root\collector" `
  -WindowStyle Minimized

Write-Host "[3/3] 포털 (next dev)" -ForegroundColor Cyan
Start-Process -FilePath "cmd.exe" `
  -ArgumentList "/c", "cd /d $root\web && npm run dev" `
  -WindowStyle Minimized

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "기동 완료 (각 창은 최소화되어 실행 중):" -ForegroundColor Green
Write-Host "  포털              http://localhost:3001"
Write-Host "  수집기 control API http://127.0.0.1:8111"
Write-Host "  관리 화면          http://localhost:3001/admin"
Write-Host ""
Write-Host "중지: docker compose stop + minimized 창 닫기"
