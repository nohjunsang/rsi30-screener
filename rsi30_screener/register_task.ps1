# register_task.ps1
# RSI30 스크리너를 미국 장 마감 후 자동 실행하도록 Windows 작업 스케줄러에 등록
#
# 사용법: 이 폴더(rsi30_screener)에서 PowerShell 열고
#   .\register_task.ps1
# 실행 (관리자 권한 필요 없음, 현재 로그인 계정 기준으로 등록됨)

$taskName = "RSI30Screener"
$scriptDir = $PSScriptRoot
$batPath = Join-Path $scriptDir "run_screener.bat"

# 미국 정규장 마감(16:00 ET)은 한국시간으로:
#   - 서머타임(EDT, 3월~11월) 적용 중: 익일 05:00 KST
#   - 표준시(EST, 11월~3월) 적용 중  : 익일 06:00 KST
# 두 경우를 다 커버하도록 06:30 KST로 여유있게 설정 (필요하면 아래 $startTime 수정)
#
# 요일 매핑 (미국 월~금 장마감 -> 한국시간 기준 다음날):
#   미국 월요일 마감 -> 한국 화요일 새벽
#   미국 화요일 마감 -> 한국 수요일 새벽
#   미국 수요일 마감 -> 한국 목요일 새벽
#   미국 목요일 마감 -> 한국 금요일 새벽
#   미국 금요일 마감 -> 한국 토요일 새벽
$startTime = "06:30"
$days = "TUE,WED,THU,FRI,SAT"

# 기존에 같은 이름의 작업이 있으면 삭제 후 재등록
schtasks /query /tn $taskName 2>$null
if ($LASTEXITCODE -eq 0) {
    schtasks /delete /tn $taskName /f | Out-Null
    Write-Host "기존 작업 삭제 후 재등록합니다."
}

schtasks /create /tn $taskName /tr "`"$batPath`"" /sc weekly /d $days /st $startTime /f

Write-Host ""
Write-Host "등록 완료: $taskName"
Write-Host "실행 시각: 매주 $days 요일, $startTime (KST)"
Write-Host "실행 파일: $batPath"
Write-Host ""
Write-Host "확인: 작업 스케줄러(taskschd.msc) 열어서 '$taskName' 검색하면 보임"
Write-Host "수동 테스트: schtasks /run /tn $taskName"
Write-Host "삭제:      schtasks /delete /tn $taskName /f"
