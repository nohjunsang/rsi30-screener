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

# ---- 거래량 급증 확인 ----
# 신호가 뜬 시점의 거래량이 평소보다 얼마나 많았는지 함께 표시.
# (거래량 자체로 새 알림을 만들진 않고, 기존 신호에 "붙는 정보"로만 씀)
VOLUME_LOOKBACK = 20                 # 평소 거래량 = 최근 N일 평균
VOLUME_SPIKE_MULTIPLIER = 1.5        # 평균 대비 이 배수 이상이면 "거래량 급증"으로 표시

# ---- RSI 다이버전스 ----
# 최근 DIVERGENCE_LOOKBACK일(봉) 중 가격 저점/고점 대비, 오늘 RSI가
# 그때보다 개선되어 있으면(가격은 신저가인데 RSI는 안 낮음/그 반대) 감지.
# 극단 구간 근처에서만 의미가 있어서 RSI_DIVERGENCE_ZONE_BUFFER로 범위 제한함
# (예: 과매도 임계값 30 + 10 = 40 이하일 때만 강세 다이버전스 인정).
DIVERGENCE_LOOKBACK = 20
RSI_DIVERGENCE_ZONE_BUFFER = 10

# ---- 타임프레임 건너 컨플루언스 ----
# 일봉 신호가 뜰 때 4시간봉도 같은 조건이 활성 상태인지(또는 그 반대)
# 확인해서, 둘 다 겹치면 "고신뢰" 표시를 붙임.
ENABLE_CROSS_TIMEFRAME_CONFLUENCE = True

# ---- 골든크로스 / 데드크로스 (이동평균선 교차) ----
# "터치"(가격이 이평선에 닿음)와는 다른 개념 - 이평선 두 개가 서로
# 교차하는 것. SMA50이 SMA200을 위로 뚫으면 골든크로스(장기 상승전환
# 신호), 아래로 뚫으면 데드크로스(장기 하락전환 신호). 자주 안 뜨는
# 대신 뜨면 의미가 큰, 전통적으로 신뢰도 높다고 평가받는 추세 신호.
SMA_CROSS_FAST = 50
SMA_CROSS_SLOW = 200

# ---- 볼린저 밴드 스퀴즈 ----
# 다른 신호들과 달리 "가격 레벨"이 아니라 "변동성"을 봄. 밴드 폭이
# 최근 BB_SQUEEZE_LOOKBACK일 중 가장 좁으면(변동성 수축) "스퀴즈 진입"
# 알림 - 조만간 큰 움직임이 올 수 있다는 사전 경고성 신호. 스퀴즈였다가
# 밴드 바깥으로 가격이 빠져나가면(변동성 확대 시작) 방향까지 같이
# "스퀴즈 해제" 알림으로 알려줌.
BB_PERIOD = 20
BB_STD_MULTIPLIER = 2.0
BB_SQUEEZE_LOOKBACK = 120

# ---- Telegram 알림 ----
# GitHub Actions에서는 Repository Secrets로 주입되는 환경변수를 그대로 사용.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
