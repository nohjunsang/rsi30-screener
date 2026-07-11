"""
h4_alerts.py
4시간봉 기준 종합 신호(RSI 과매도/회복, SMA120/200 터치, 일목균형표 구름대
터치 + 상방/하방 돌파) 스캔 - 일봉과 동일한 조건들을 4시간봉에도 똑같이
적용하되, 구름대 상방/하방 "돌파"(above/below 진입) 알림은 4시간봉에서만
켜짐 (enable_cloud_breakout=True).

주의: SMA120/200, 일목균형표(9/26/52)의 "기간 숫자"는 일봉/4시간봉 구분 없이
그대로 재사용함. 즉 4시간봉에서 SMA120은 "120개의 4시간봉"(대략 20 거래일
정도) 기준이라, 일봉 SMA120("120 거래일", 대략 6개월)과 룩백 기간 자체는
다름 - 같은 이름이지만 "더 짧은 호흡"의 신호로 이해하면 됨.

4시간봉 RSI/터치는 "잠정치" 성격이 강함 (일봉보다 훨씬 자주 신호가
나오는 대신, 노이즈도 많음).
"""

from indicators import resample_to_4h
from data import get_scan_universe, download_hourly_data, extract_ticker_df
from engine import scan
from state import StateStore

STATE_FILENAME = "h4_state.json"


def scan_h4_alerts(state_filename: str = None):
    """반환: (new_alerts: list[dict], state: StateStore)
    state_filename을 넘기면 기본 상태파일 대신 그걸 사용함 (테스트용 임시파일 등)"""
    state_filename = state_filename or STATE_FILENAME
    tickers = get_scan_universe()
    print(f"[4H] 스캔 대상 종목 수: {len(tickers)}")

    if not tickers:
        return [], StateStore(state_filename)

    hourly = download_hourly_data(tickers)

    def get_df(ticker):
        df = extract_ticker_df(hourly, ticker)
        if df is None or df.empty:
            return None
        return resample_to_4h(df.dropna(subset=["Close"]))

    return scan(tickers, get_df, state_filename, label="[4H] ", enable_cloud_breakout=True)
