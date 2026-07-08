"""
screener.py
시총 3000억달러 이상 + 일봉 RSI(14) <= 30 종목 스크리닝
"""

import time
import pandas as pd

from config import MARKET_CAP_THRESHOLD, RSI_PERIOD, RSI_THRESHOLD
from data import get_sp500_tickers, download_price_data, get_market_cap
from indicators import wilder_rsi


def screen(
    market_cap_threshold: float = MARKET_CAP_THRESHOLD,
    rsi_threshold: float = RSI_THRESHOLD,
    rsi_period: int = RSI_PERIOD,
) -> pd.DataFrame:
    """
    market_cap_threshold : 시가총액 하한선 (달러 단위, 예: 300B = 300_000_000_000)
    rsi_threshold        : RSI 상한선 (이 값 이하인 종목만 통과)
    rsi_period            : RSI 계산 기간

    기본값은 config.py 값을 쓰고, 필요하면 호출할 때 덮어쓸 수 있음
    (main.py에서 커맨드라인 인자로 넘겨받아 여기로 전달함).
    """
    tickers = get_sp500_tickers()
    print(f"대상 티커 수: {len(tickers)}")
    print(f"조건: 시총 >= ${market_cap_threshold / 1e9:.0f}B, RSI({rsi_period}) <= {rsi_threshold}")

    data = download_price_data(tickers)

    results = []

    for ticker in tickers:
        try:
            close = data[ticker]["Close"].dropna()
            if len(close) < rsi_period + 1:
                continue

            rsi_series = wilder_rsi(close, rsi_period)
            latest_rsi = rsi_series.iloc[-1]
            latest_close = close.iloc[-1]
            latest_date = close.index[-1].strftime("%Y-%m-%d")

            if pd.isna(latest_rsi) or latest_rsi > rsi_threshold:
                continue

            market_cap = get_market_cap(ticker)
            if market_cap is None or market_cap < market_cap_threshold:
                continue

            prev_close = close.iloc[-2] if len(close) >= 2 else None
            change_pct = (
                (latest_close - prev_close) / prev_close * 100
                if prev_close
                else None
            )

            results.append(
                {
                    "ticker": ticker,
                    "date": latest_date,
                    "close": round(float(latest_close), 2),
                    "change_pct": round(float(change_pct), 2) if change_pct is not None else None,
                    "rsi": round(float(latest_rsi), 2),
                    "market_cap_B": round(market_cap / 1e9, 1),
                }
            )
            time.sleep(0.1)  # 레이트리밋 방지

        except Exception:
            continue

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values("rsi")
    return df
