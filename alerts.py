"""
alerts.py
일봉 기준 종합 신호(RSI 과매도/과매수 진입·회복, SMA120/200 터치, 일목균형표
구름대 터치 + 상방/하방 돌파, RSI 다이버전스) 스캔. 거래량 급증 여부는
기존 신호에 부가 정보로 붙고, 4시간봉과의 컨플루언스도 함께 확인함.
실제 신호 계산/전이감지 로직은 engine.py에 공용으로 있음.
"""

from data import get_scan_universe, download_daily_data, extract_ticker_df
from engine import scan
from state import StateStore

STATE_FILENAME = "daily_state.json"


def scan_daily_alerts(state_filename: str = None):
    """반환: (new_alerts: list[dict], state: StateStore)
    state_filename을 넘기면 기본 상태파일 대신 그걸 사용함 (테스트용 임시파일 등)"""
    state_filename = state_filename or STATE_FILENAME
    tickers = get_scan_universe()
    print(f"스캔 대상 종목 수: {len(tickers)}")

    if not tickers:
        return [], StateStore(state_filename)

    data = download_daily_data(tickers)

    def get_df(ticker):
        return extract_ticker_df(data, ticker)

    return scan(
        tickers,
        get_df,
        state_filename,
        enable_cloud_breakout=True,
        cross_state_filename="h4_state.json",
        cross_label="4H",
    )
