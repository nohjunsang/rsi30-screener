"""
config.py
스크리너 설정값 모음
"""

# ---- 스크리닝 조건 ----
MARKET_CAP_THRESHOLD = 300_000_000_000   # 시가총액 하한선 (3000억 달러)
RSI_PERIOD = 14                          # RSI 계산 기간
RSI_THRESHOLD = 30                       # RSI 상한선 (이하일 때 오버셀드로 판단)
LOOKBACK_DAYS = "6mo"                    # RSI 계산용 가격 데이터 조회 기간

# ---- 실시간 모니터링 (realtime_monitor.py) ----
REALTIME_POLL_INTERVAL_SECONDS = 300     # 몇 초마다 재확인할지 (기본 5분)

# ---- Telegram 알림 (안 쓰면 빈 값으로 둘 것) ----
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
