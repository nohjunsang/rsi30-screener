@echo off
REM run_screener.bat
REM 이 배치 파일이 있는 폴더로 자동 이동한 뒤 스크리너 실행
REM (Task Scheduler는 기본 작업 폴더를 잡아주지 않아서 필요함)

cd /d "%~dp0"

echo [%date% %time%] 스크리너 실행 시작 >> run_log.txt
python main.py >> run_log.txt 2>&1
echo [%date% %time%] 스크리너 실행 종료 >> run_log.txt
