@echo off
REM run_intraday.bat
REM Moves to this script's folder then runs the 4H intraday monitor.
REM (Legacy/local backup script - main automation now runs via GitHub Actions)

cd /d "%~dp0"

echo [%date% %time%] intraday_monitor.py run >> intraday_log.txt
python intraday_monitor.py >> intraday_log.txt 2>&1
