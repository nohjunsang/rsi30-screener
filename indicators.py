"""
indicators.py
기술적 지표 계산 (RSI, SMA 터치, 일목균형표 구름대 터치, 4시간봉 리샘플링)
"""

import pandas as pd


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI (표준 RSI 계산 방식, 대부분 증권사 차트와 동일)"""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def sma_touch(close: pd.Series, period: int, tolerance_pct: float):
    """
    종가가 SMA(period)선 ±tolerance_pct% 안에 들어오는지 판정.
    반환: (is_touching: bool, sma_value: float|None, distance_pct: float|None)
    """
    if len(close) < period:
        return False, None, None

    sma_value = close.rolling(period).mean().iloc[-1]
    if pd.isna(sma_value) or sma_value == 0:
        return False, None, None

    latest_close = close.iloc[-1]
    distance_pct = abs(latest_close - sma_value) / sma_value * 100
    touching = distance_pct <= tolerance_pct

    return bool(touching), float(sma_value), float(distance_pct)


def ichimoku_position(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    tenkan_period: int,
    kijun_period: int,
    senkou_b_period: int,
    displacement: int,
    tolerance_pct: float,
):
    """
    일목균형표 구름대(선행스팬 A/B) 기준 현재가의 위치를 판정.

    선행스팬은 계산 시점 기준 displacement만큼 '미래'에 표시되는 값이라,
    오늘 차트에 실제로 그려진 구름대 값을 얻으려면 계산된 시리즈를
    displacement만큼 뒤로(shift) 밀어줘야 함.

    반환: (position, cloud_top, cloud_bottom)
      position: "top"(상단 터치) | "bottom"(하단 터치) | "inside"(구름 안)
                | "above"(구름 위) | "below"(구름 아래) | None(계산 불가)
    """
    tenkan = (high.rolling(tenkan_period).max() + low.rolling(tenkan_period).min()) / 2
    kijun = (high.rolling(kijun_period).max() + low.rolling(kijun_period).min()) / 2

    senkou_a_raw = (tenkan + kijun) / 2
    senkou_b_raw = (high.rolling(senkou_b_period).max() + low.rolling(senkou_b_period).min()) / 2

    senkou_a = senkou_a_raw.shift(displacement)
    senkou_b = senkou_b_raw.shift(displacement)

    a_val = senkou_a.iloc[-1]
    b_val = senkou_b.iloc[-1]

    if pd.isna(a_val) or pd.isna(b_val):
        return None, None, None

    cloud_top = max(a_val, b_val)
    cloud_bottom = min(a_val, b_val)
    latest_close = close.iloc[-1]

    top_dist = abs(latest_close - cloud_top) / cloud_top * 100 if cloud_top else None
    bottom_dist = abs(latest_close - cloud_bottom) / cloud_bottom * 100 if cloud_bottom else None

    if top_dist is not None and top_dist <= tolerance_pct:
        position = "top"
    elif bottom_dist is not None and bottom_dist <= tolerance_pct:
        position = "bottom"
    elif cloud_bottom <= latest_close <= cloud_top:
        position = "inside"
    elif latest_close > cloud_top:
        position = "above"
    else:
        position = "below"

    return position, float(cloud_top), float(cloud_bottom)


def resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    """1시간봉 OHLC 데이터프레임을 4시간봉으로 리샘플링.
    (yfinance가 4h 인터벌을 직접 제공하지 않아서 60m 데이터를 묶어서 만듦)

    주의: 미국 정규장(09:30~16:00 ET, 6.5시간)은 4시간으로 딱 안 나눠떨어져서
    실제 거래소 4시간봉 차트와 봉 경계가 완벽히 일치하진 않는 근사치임.
    """
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in df.columns:
        agg["Volume"] = "sum"
    resampled = df.resample("4h", origin="start_day").agg(agg).dropna(how="all")
    return resampled
