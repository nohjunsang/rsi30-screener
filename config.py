"""
config.py
스크리너 설정값 모음
"""

import os

# ---- 유니버스 ----
# 요청에 따라 S&P500 단일 유니버스로 한정 (S&P400/600 확장 제거)
UNIVERSE_INDICES = ["sp500"]

# 레버리지 ETF 등, 시가총액 개념이 안 맞거나 유니버스에 안 잡히는 개별
# 종목을 항상 감시 대상에 포함시키고 싶을 때 여기에 추가/삭제
EXTRA_WATCHLIST = ["SOXL", "NAIL", "TSLQ"]

# 섹터(GICS 기준)별 시가총액 상위 N개는 MARKET_CAP_THRESHOLD 미만이어도
# 항상 감시 대상에 포함 (토스증권의 "산업별 시총 순위"와 정확히 같은
# 분류는 아니고, 표준 GICS 11개 섹터 분류를 대신 사용함 - 참고)
SECTOR_TOP_N = 10

# ---- 스크리닝 조건 ----
MARKET_CAP_THRESHOLD = 100_000_000_000   # 시가총액 하한선 (1000억 달러)
RSI_PERIOD = 14
RSI_THRESHOLD = 30                        # 이 값 이하면 과매도 진입 / 위로 올라오면 회복
RSI_OVERBOUGHT_THRESHOLD = 70              # 이 값 이상이면 과매수 진입 / 아래로 내려오면 이탈
LOOKBACK_DAYS = "2y"                        # SMA200/일목균형표 계산 위해 넉넉하게

# ---- 이동평균선 터치 ----
SMA_TOUCH_PERIODS = [120, 200]
SMA_TOUCH_TOLERANCE_PCT = 1.0              # 이 %이내로 근접하면 "터치"로 판단

# ---- 일목균형표(Ichimoku) 구름대 터치/돌파 ----
ICHIMOKU_TENKAN = 9
ICHIMOKU_KIJUN = 26
ICHIMOKU_SENKOU_B = 52
ICHIMOKU_DISPLACEMENT = 26
ICHIMOKU_TOUCH_TOLERANCE_PCT = 1.0

# ---- 4시간봉 (장중 조기경보용) ----
# RSI/SMA/일목 조건 자체는 위 값들을 일봉과 동일하게 그대로 재사용함
# (engine.py가 타임프레임 공용 로직이라 별도 4h 전용 임계값은 없음)
H4_LOOKBACK_PERIOD = "60d"    # yfinance 60분봉은 최대 730일까지 가능, 60일이면 4h RSI(14) 계산에 충분

# ---- Telegram 알림 ----
# GitHub Actions에서는 Repository Secrets로 주입되는 환경변수를 그대로 사용.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
