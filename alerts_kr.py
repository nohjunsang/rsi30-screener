"""
alerts_kr.py
alerts.py의 국내주식 버전. 유니버스만 kr_universe.py(코스피 시총 상위 50위)로
바꾸고, 시세 다운로드는 toss_data.py를 그대로 재사용 (국내 종목 코드도 이미
지원됨을 실측으로 확인함 - 파라미터/응답 형식이 미국 종목과 동일).

4시간봉 컨플루언스는 아직 없음 - intraday_monitor.py가 야후파이낸스 기반인데
국내 종목 4시간봉 데이터 안정성이 아직 검증 안 됐어서, 우선 일봉만 지원.
"""

from kr_universe import get_kr_universe
from toss_data import download_daily_data, extract_ticker_df
from engine import scan
from state import StateStore

STATE_FILENAME = "kr_daily_state.json"


def scan_kr_daily_alerts(state_filename: str = None):
    """반환: (new_alerts: list[dict], state: StateStore)
    state_filename을 넘기면 기본 상태파일 대신 그걸 사용함 (테스트용 임시파일 등)"""
    state_filename = state_filename or STATE_FILENAME
    universe_df = get_kr_universe(top_n=50)
    tickers = universe_df["Symbol"].tolist()
    print(f"국장 스캔 대상 종목 수: {len(tickers)}")
    if not tickers:
        return [], StateStore(state_filename)

    data = download_daily_data(tickers)

    def get_df(ticker):
        return extract_ticker_df(data, ticker)

    return scan(
        tickers,
        get_df,
        state_filename,
        enable_cloud_breakout=False,  # 미국주식과 동일하게 비활성화 (백테스트 결과 반영)
        market="KR_STOCK",
    )
