"""
signals.py
일봉 또는 4시간봉 OHLC 데이터로 각 지표의 "현재 원시 상태값"을 계산.
(과거 상태와 비교해서 "새로운 신호인지" 판단하는 건 engine.py의 역할이고,
 이 모듈은 순수하게 "지금 이 순간의 지표값"만 계산함 - 타임프레임 무관 공용)
"""

import pandas as pd

from indicators import wilder_rsi, sma_touch, ichimoku_position
from config import (
    RSI_PERIOD,
    RSI_THRESHOLD,
    RSI_OVERBOUGHT_THRESHOLD,
    SMA_TOUCH_PERIODS,
    SMA_TOUCH_TOLERANCE_PCT,
    ICHIMOKU_TENKAN,
    ICHIMOKU_KIJUN,
    ICHIMOKU_SENKOU_B,
    ICHIMOKU_DISPLACEMENT,
    ICHIMOKU_TOUCH_TOLERANCE_PCT,
)


def compute_signals(df: pd.DataFrame) -> dict:
    """
    df: ['Open','High','Low','Close'] 컬럼을 가진 OHLC DataFrame (시간순 오름차순)
        일봉이든 4시간봉이든 동일하게 사용 가능.

    반환 (모든 값은 "현재 시점의 원시 상태", 신규 여부 판단은 engine.py에서):
    {
        "close": float, "change_pct": float,
        "rsi": float,
        "rsi_zone": "oversold" | "overbought" | "normal",
        "sma_touches": [{"period":120,"touching":bool,"value":..,"distance_pct":..}, ...],
        "ichimoku": {"position": "top"|"bottom"|"inside"|"above"|"below",
                     "cloud_top":.., "cloud_bottom":..} | None,
    }
    """
    close = df["Close"].dropna()
    high = df["High"].dropna()
    low = df["Low"].dropna()

    if len(close) < RSI_PERIOD + 1:
        return None

    latest_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2]) if len(close) >= 2 else None
    change_pct = (
        round((latest_close - prev_close) / prev_close * 100, 2) if prev_close else None
    )

    # ---- RSI (과매도/과매수 양쪽 다 판정) ----
    rsi_series = wilder_rsi(close, RSI_PERIOD)
    latest_rsi = rsi_series.iloc[-1]
    rsi_value = round(float(latest_rsi), 2) if not pd.isna(latest_rsi) else None

    if rsi_value is None:
        rsi_zone = "normal"
    elif rsi_value <= RSI_THRESHOLD:
        rsi_zone = "oversold"
    elif rsi_value >= RSI_OVERBOUGHT_THRESHOLD:
        rsi_zone = "overbought"
    else:
        rsi_zone = "normal"

    # ---- SMA 터치 ----
    sma_touches = []
    for period in SMA_TOUCH_PERIODS:
        if len(close) < period:
            sma_touches.append({"period": period, "touching": False, "value": None, "distance_pct": None})
            continue
        is_touching, sma_value, distance_pct = sma_touch(close, period, SMA_TOUCH_TOLERANCE_PCT)
        sma_touches.append(
            {
                "period": period,
                "touching": bool(is_touching),
                "value": round(sma_value, 2) if sma_value else None,
                "distance_pct": round(distance_pct, 2) if distance_pct else None,
            }
        )

    # ---- 일목균형표 구름대 위치 ----
    ichimoku_result = None
    if len(close) >= ICHIMOKU_SENKOU_B + ICHIMOKU_DISPLACEMENT:
        position, cloud_top, cloud_bottom = ichimoku_position(
            high,
            low,
            close,
            ICHIMOKU_TENKAN,
            ICHIMOKU_KIJUN,
            ICHIMOKU_SENKOU_B,
            ICHIMOKU_DISPLACEMENT,
            ICHIMOKU_TOUCH_TOLERANCE_PCT,
        )
        if position is not None:
            ichimoku_result = {
                "position": position,
                "cloud_top": round(cloud_top, 2),
                "cloud_bottom": round(cloud_bottom, 2),
            }

    return {
        "close": round(latest_close, 2),
        "change_pct": change_pct,
        "rsi": rsi_value,
        "rsi_zone": rsi_zone,
        "sma_touches": sma_touches,
        "ichimoku": ichimoku_result,
    }
