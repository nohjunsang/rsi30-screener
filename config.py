"""
config.py
스크리너 설정값 모음
"""

import os

# ---- 스크리닝 조건 ----
MARKET_CAP_THRESHOLD = 300_000_000_000   # 시가총액 하한선 (3000억 달러)
RSI_PERIOD = 14                          # RSI 계산 기간
RSI_THRESHOLD = 30                       # RSI 상한선 (이하일 때 오버셀드로 판단)
LOOKBACK_DAYS = "6mo"                    # RSI 계산용 가격 데이터 조회 기간

# ---- Telegram 알림 ----
# GitHub Actions에서는 Repository Secrets로 주입되는 환경변수를 그대로 사용.
# 로컬(Windows)에서 테스트할 때는 환경변수가 없으면 아래 빈 문자열 대신
# 직접 값을 채워넣어도 됨 (단, 이 파일을 공개 GitHub 저장소에 올릴 경우
# 토큰이 그대로 노출되니 로컬 테스트 후에는 다시 빈 값으로 되돌릴 것).
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
