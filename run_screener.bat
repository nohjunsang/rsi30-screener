@echo off
REM run_screener.bat
REM Moves to this script's folder then runs the daily (EOD) screener.
REM (Legacy/local backup script - main automation now runs via GitHub Actions)

cd /d "%~dp0"

echo [%date% %time%] main.py run started >> run_log.txt
python main.py >> run_log.txt 2>&1
echo [%date% %time%] main.py run finished >> run_log.txt
