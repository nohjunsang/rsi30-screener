"""
data.py
캐시(universe_cache.json) 기반 스캔 유니버스 조회 + 가격 데이터 다운로드.

universe_cache.json은 refresh_cache.py가 만들며, {ticker: {sector, market_cap}}
형태의 전체 유니버스 정보와, 시총 기준과 무관하게 항상 포함할 티커 목록
(always_include = 섹터별 top N + 관심종목)을 담고 있음.
"""

import json
from pathlib import Path

import pandas as pd
import yfinance as yf

from config import LOOKBACK_DAYS, H4_LOOKBACK_PERIOD, MARKET_CAP_THRESHOLD

CACHE_FILE = Path(__file__).parent / "universe_cache.json"

_cache_memo = None


def _load_cache():
    global _cache_memo
    if _cache_memo is not None:
        return _cache_memo
    if not CACHE_FILE.exists():
        return None
    try:
        _cache_memo = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return _cache_memo


def get_scan_universe() -> list[str]:
    """
    캐시에서 (시가총액 >= MARKET_CAP_THRESHOLD 인 종목) + (always_include:
    섹터별 시총 top N + 관심종목)을 합쳐서 스캔 대상 티커 리스트 반환.
    캐시가 없으면 빈 리스트 (refresh_cache.py를 먼저 실행해야 함).
    """
    cache = _load_cache()
    if not cache:
        return []

    records = cache.get("universe", {})
    always_include = set(cache.get("always_include", []))

    result = set(always_include)
    for ticker, info in records.items():
        cap = info.get("market_cap")
        if cap is not None and cap >= MARKET_CAP_THRESHOLD:
            result.add(ticker)

    return sorted(result)


def get_market_cap_from_cache(ticker: str):
    cache = _load_cache()
    if not cache:
        return None
    return cache.get("universe", {}).get(ticker, {}).get("market_cap")


def download_daily_data(tickers: list[str]) -> pd.DataFrame:
    """일봉 OHLC 배치 다운로드 (RSI/SMA/일목균형표 계산용)"""
    return yf.download(
        tickers,
        period=LOOKBACK_DAYS,
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )


def download_hourly_data(tickers: list[str]) -> pd.DataFrame:
    """1시간봉 배치 다운로드 (4시간봉 리샘플링용).
    prepost=True로 프리마켓(장전)/애프터마켓(장후) 데이터도 포함함
    (정규장 09:30~16:00 ET뿐 아니라 04:00~20:00 ET 전체 커버)."""
    return yf.download(
        tickers,
        period=H4_LOOKBACK_PERIOD,
        interval="60m",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
        prepost=True,
    )


def extract_ticker_df(data: pd.DataFrame, ticker: str):
    """다중 티커 yf.download 결과에서 개별 티커의 OHLC(+Volume) DataFrame 추출.
    실패 시 None 반환 (해당 티커 스킵 처리용)"""
    try:
        if isinstance(data.columns, pd.MultiIndex):
            df = data[ticker]
        else:
            df = data
        cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
        if not cols:
            return None
        df = df[cols].dropna(how="all")
        return df
    except (KeyError, Exception):
        return None


def download_latest_quote(tickers: list[str]) -> dict[str, dict]:
    """프리마켓/애프터마켓 포함 가장 최근 체결가를 1분봉으로 조회
    (RSI/SMA 등 신호 계산에는 안 쓰고, 리마인더 메시지에 "지금 가격"만
    보여주는 용도 - 정규장 종가 기준 신호 계산 자체는 안 바뀜).

    반환: {ticker: {"price": float, "as_of": Timestamp}}
    조회 실패했거나 데이터가 없는 종목은 결과에서 빠짐(에러를 던지지 않음 -
    실패해도 호출부가 "정규장 종가만 표시"로 조용히 폴백할 수 있게).
    """
    if not tickers:
        return {}
    try:
        data = yf.download(
            tickers,
            period="2d",
            interval="1m",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
            prepost=True,
        )
    except Exception:
        return {}

    quotes = {}
    for ticker in tickers:
        df = extract_ticker_df(data, ticker)
        if df is None or df.empty:
            continue
        last = df.dropna(subset=["Close"]).tail(1)
        if last.empty:
            continue
        quotes[ticker] = {
            "price": round(float(last["Close"].iloc[0]), 2),
            "as_of": last.index[0],
        }
    return quotes
