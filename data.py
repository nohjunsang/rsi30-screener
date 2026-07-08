"""
data.py
S&P500 티커 목록 및 가격 데이터 수집
"""

import io

import pandas as pd
import requests
import yfinance as yf

from config import LOOKBACK_DAYS


def get_sp500_tickers() -> list[str]:
    """S&P500 구성종목 티커 리스트를 위키피디아에서 가져옴.
    시총 3000억달러 이상 기업은 거의 전부 S&P500에 포함되어 있어
    이 유니버스만으로도 스크리닝 커버리지는 충분함.

    위키피디아가 User-Agent 없는 요청을 403으로 막기 때문에
    requests로 먼저 받아온 뒤 pandas에 넘겨줌.
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    table = pd.read_html(io.StringIO(resp.text))[0]
    tickers = table["Symbol"].str.replace(".", "-", regex=False).tolist()
    return tickers


def download_price_data(tickers: list[str]) -> pd.DataFrame:
    """전체 티커에 대해 일봉 데이터를 배치로 다운로드"""
    data = yf.download(
        tickers,
        period=LOOKBACK_DAYS,
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )
    return data


def get_market_cap(ticker: str):
    """개별 티커의 시가총액 조회 (RSI 조건 통과한 종목만 호출해서 API 절약)"""
    info = yf.Ticker(ticker).fast_info
    return info.get("market_cap") or info.get("marketCap")
