"""
kr_universe.py
코스피 시가총액 상위 종목 수집 (pykrx로 한국거래소 정보데이터시스템 조회).
universe.py(S&P500/400/600, 위키피디아 스크래핑)와 같은 역할이지만 소스는 다름.

⚠️ 실행 전 꼭 확인할 것 - KRX 정회원 계정 필요
pykrx가 최근 정책 변경으로 data.krx.co.kr 정회원 계정 로그인이 필요해짐.
환경변수(.env에서 로딩): KRX_ID, KRX_PW
"""

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def get_kr_universe(top_n: int = 50, market: str = "KOSPI") -> pd.DataFrame:
    """
    반환: DataFrame[Symbol, Name] (시가총액 상위 top_n개, 내림차순)

    market: "KOSPI" 또는 "KOSDAQ". 코스닥까지 다루게 되면 두 번 호출해서
    합치면 됨 (get_kr_universe("KOSPI") + get_kr_universe("KOSDAQ")).
    """
    from pykrx import stock

    date = stock.get_nearest_business_day_in_a_week()
    df = stock.get_market_cap(date, market=market)
    df = df.sort_values("시가총액", ascending=False).head(top_n)

    tickers = df.index.tolist()
    names = [stock.get_market_ticker_name(t) for t in tickers]

    return pd.DataFrame({"Symbol": tickers, "Name": names})
