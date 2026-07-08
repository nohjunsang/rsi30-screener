# register_intraday_task.ps1
# 장중 모니터링(intraday_monitor.py)을 15분 간격으로 상시 실행되도록 등록.
# 스크립트 자체가 "지금 미국 장중인지"를 zoneinfo로 판단해서
# 장중이 아니면 바로 종료하므로, 굳이 시간대(KST) 계산해서
# 스케줄러에 시작/종료 시각을 넣을 필요가 없음 (서머타임도 자동 처리됨).
#
# 사용법: 이 폴더에서 PowerShell 열고
#   powershell -ExecutionPolicy Bypass -File .\register_intraday_task.ps1

$taskName = "RSI30IntradayMonitor"
$scriptDir = $PSScriptRoot
$batPath = Join-Path $scriptDir "run_intraday.bat"

$intervalMinutes = 15   # 체크 주기 (원하면 조절 가능, 너무 짧으면 API 부하/레이트리밋 위험)

# 기존 작업 있으면 삭제 후 재등록
schtasks /query /tn $taskName 2>$null
if ($LASTEXITCODE -eq 0) {
    schtasks /delete /tn $taskName /f | Out-Null
    Write-Host "기존 작업 삭제 후 재등록합니다."
}

# 매일 00:00부터 매 15분마다 상시 반복 실행 (하루 종일 돌지만
# 장 시간 아니면 스크립트가 즉시 종료되므로 실제 부하는 거의 없음)
schtasks /create /tn $taskName /tr "`"$batPath`"" /sc minute /mo $intervalMinutes /st 00:00 /f

Write-Host ""
Write-Host "등록 완료: $taskName"
Write-Host "체크 주기: $intervalMinutes 분 (24시간 상시, 장중 아니면 스크립트가 자동 스킵)"
Write-Host "실행 파일: $batPath"
Write-Host ""
Write-Host "확인: schtasks /query /tn $taskName"
Write-Host "삭제: schtasks /delete /tn $taskName /f"
