@echo off
REM run_intraday.bat
REM 장중 모니터링(intraday_monitor.py) 실행용 배치 파일

cd /d "%~dp0"

echo [%date% %time%] intraday_monitor 실행 >> intraday_log.txt
python intraday_monitor.py >> intraday_log.txt 2>&1
