"""
alerts.py
일봉 기준 종합 신호(RSI 과매도/회복, SMA120/200 터치, 일목균형표 구름대
터치 + 상방/하방 돌파) 스캔. 실제 신호 계산/전이감지 로직은 engine.py에
공용으로 있음.
"""

from data import get_scan_universe, download_daily_data, extract_ticker_df
from engine import scan
from state import StateStore

STATE_FILENAME = "daily_state.json"


def scan_daily_alerts():
    """반환: (new_alerts: list[dict], state: StateStore)"""
    tickers = get_scan_universe()
    print(f"스캔 대상 종목 수: {len(tickers)}")

    if not tickers:
        return [], StateStore(STATE_FILENAME)

    data = download_daily_data(tickers)

    def get_df(ticker):
        return extract_ticker_df(data, ticker)

    return scan(tickers, get_df, STATE_FILENAME, enable_cloud_breakout=True)
