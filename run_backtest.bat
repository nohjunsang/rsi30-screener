@echo off
REM run_backtest.bat
REM 캐시된 전체 유니버스로 최근 2년치 백테스트 실행 + 텔레그램 전송
REM 기준 기간: 2주(10거래일) / 1개월(20거래일)
REM (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 setx로 등록되어 있어야 함)
REM
REM 다른 옵션으로 돌리고 싶으면 이 파일 대신 직접:
REM   python backtest.py --tickers AAPL,MSFT --years 3 --horizons 5,10,20 --telegram

cd /d "%~dp0"
python backtest.py --years 2 --horizons 10,20 --telegram
