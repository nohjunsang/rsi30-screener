@echo off
REM run_backtest.bat
REM Full cached universe backtest, last 2 years, sends summary to Telegram.
REM Requires TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID env vars (set via setx once).
REM For other options, run backtest.py directly instead of this file.

cd /d "%~dp0"
python backtest.py --years 2 --horizons 10,20 --telegram
