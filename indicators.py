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


def sma_cross_position(close: pd.Series, fast_period: int, slow_period: int):
    """
    골든크로스/데드크로스 판정용: 빠른 이평선(fast)이 느린 이평선(slow)보다
    위에 있는지 아래에 있는지 현재 위치만 반환 (상태 전이 감지는 engine.py에서).

    반환: "above"(골든크로스 상태) | "below"(데드크로스 상태) | None(데이터 부족)
    """
    if len(close) < slow_period:
        return None

    fast = close.rolling(fast_period).mean().iloc[-1]
    slow = close.rolling(slow_period).mean().iloc[-1]

    if pd.isna(fast) or pd.isna(slow):
        return None

    return "above" if fast > slow else "below"


def bollinger_bands(close: pd.Series, period: int, std_multiplier: float):
    """볼린저 밴드 상단/중단/하단 계산. 반환: (upper, middle, lower) - 각각 마지막 값(float) 또는 None"""
    if len(close) < period:
        return None, None, None

    window = close.rolling(period)
    middle = window.mean().iloc[-1]
    std = window.std().iloc[-1]

    if pd.isna(middle) or pd.isna(std):
        return None, None, None

    upper = middle + std_multiplier * std
    lower = middle - std_multiplier * std
    return float(upper), float(middle), float(lower)


def bb_squeeze_state(close: pd.Series, period: int, std_multiplier: float, lookback: int):
    """
    볼린저 밴드 스퀴즈(변동성 수축) 여부 판정.
    "밴드 폭이 최근 lookback일 중 가장 좁다"를 스퀴즈로 정의함.

    반환: dict {
        "is_squeeze": bool,           # 지금이 스퀴즈 상태인지
        "bandwidth": float,            # 현재 밴드폭 비율 ((상단-하단)/중단)
        "upper": float, "lower": float,
        "breakout": "up"|"down"|None,  # 스퀴즈 중이 아니면, 밴드 바깥으로 뚫었는지
    }
    또는 데이터 부족 시 None
    """
    if len(close) < period + lookback:
        return None

    window = close.rolling(period)
    middle = window.mean()
    std = window.std()
    upper = middle + std_multiplier * std
    lower = middle - std_multiplier * std
    bandwidth = (upper - lower) / middle

    recent_bandwidth = bandwidth.iloc[-lookback:].dropna()
    current_bw = bandwidth.iloc[-1]

    if pd.isna(current_bw) or len(recent_bandwidth) < lookback // 2:
        return None

    # "정확히 최솟값인 딱 하루"만 스퀴즈로 잡으면 너무 빡빡해서(노이즈에 취약),
    # 최근 lookback일 중 하위 10% 구간에 들어오면 스퀴즈로 인정함
    squeeze_cutoff = recent_bandwidth.quantile(0.10)
    is_squeeze = bool(current_bw <= squeeze_cutoff)

    latest_close = close.iloc[-1]
    latest_upper = upper.iloc[-1]
    latest_lower = lower.iloc[-1]

    breakout = None
    if not is_squeeze:
        if latest_close > latest_upper:
            breakout = "up"
        elif latest_close < latest_lower:
            breakout = "down"

    return {
        "is_squeeze": is_squeeze,
        "bandwidth": round(float(current_bw) * 100, 2),
        "upper": round(float(latest_upper), 2) if not pd.isna(latest_upper) else None,
        "lower": round(float(latest_lower), 2) if not pd.isna(latest_lower) else None,
        "breakout": breakout,
    }


def detect_divergence(
    close: pd.Series,
    rsi: pd.Series,
    lookback: int,
    oversold_threshold: float,
    overbought_threshold: float,
    zone_buffer: float,
):
    """
    가격과 RSI 사이의 다이버전스(이격) 감지. 미래 데이터를 안 쓰는 인과적
    (causal, non-repainting) 방식이라 실시간 스캔에 그대로 쓸 수 있음.

    방식: "오늘 이전 lookback개 봉" 중 가격의 최저/최고점을 기준점으로 잡고,
    오늘 가격이 그 기준점 수준으로 다시 근접/갱신했는데 RSI는 그때보다
    개선(약세/과열 압력이 줄어듦)되어 있으면 다이버전스로 판정.

    반환: (kind, detail)
      kind: "bullish" | "bearish" | None
      detail: {"ref_date":.., "ref_price":.., "ref_rsi":.., "today_price":.., "today_rsi":..} | None
    """
    if len(close) < lookback + 2:
        return None, None

    window_close = close.iloc[-(lookback + 1) : -1]  # 오늘 제외
    window_rsi = rsi.iloc[-(lookback + 1) : -1]

    today_price = close.iloc[-1]
    today_rsi = rsi.iloc[-1]

    if pd.isna(today_rsi) or window_rsi.isna().all():
        return None, None

    # ---- 강세 다이버전스: 가격 신저가(근접) + RSI는 그때보다 높음 (과매도 구간 근처에서만 유의미) ----
    ref_low_idx = window_close.idxmin()
    ref_low_price = window_close.loc[ref_low_idx]
    ref_low_rsi = window_rsi.loc[ref_low_idx]

    if (
        not pd.isna(ref_low_rsi)
        and today_price <= ref_low_price * 1.002  # 0.2% 오차 허용
        and today_rsi > ref_low_rsi
        and today_rsi <= oversold_threshold + zone_buffer
    ):
        return "bullish", {
            "ref_date": ref_low_idx,
            "ref_price": round(float(ref_low_price), 2),
            "ref_rsi": round(float(ref_low_rsi), 2),
            "today_price": round(float(today_price), 2),
            "today_rsi": round(float(today_rsi), 2),
        }

    # ---- 약세 다이버전스: 가격 신고가(근접) + RSI는 그때보다 낮음 (과매수 구간 근처에서만 유의미) ----
    ref_high_idx = window_close.idxmax()
    ref_high_price = window_close.loc[ref_high_idx]
    ref_high_rsi = window_rsi.loc[ref_high_idx]

    if (
        not pd.isna(ref_high_rsi)
        and today_price >= ref_high_price * 0.998
        and today_rsi < ref_high_rsi
        and today_rsi >= overbought_threshold - zone_buffer
    ):
        return "bearish", {
            "ref_date": ref_high_idx,
            "ref_price": round(float(ref_high_price), 2),
            "ref_rsi": round(float(ref_high_rsi), 2),
            "today_price": round(float(today_price), 2),
            "today_rsi": round(float(today_rsi), 2),
        }

    return None, None


def volume_spike_ratio(volume: pd.Series, lookback: int) -> float:
    """오늘 거래량이 최근 lookback일 평균 거래량 대비 몇 배인지 반환"""
    if volume is None or len(volume) < lookback + 1:
        return None
    avg_vol = volume.iloc[-(lookback + 1) : -1].mean()
    if pd.isna(avg_vol) or avg_vol == 0:
        return None
    today_vol = volume.iloc[-1]
    if pd.isna(today_vol):
        return None
    return float(today_vol / avg_vol)


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


def ichimoku_position_series(
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
    ichimoku_position()의 벡터화 버전 - 마지막 시점 하나가 아니라 전체
    기간에 대해 날짜별 position을 한 번에 계산함 (백테스트용, 훨씬 빠름).

    반환: (position: pd.Series[object], cloud_top: pd.Series, cloud_bottom: pd.Series)
    """
    tenkan = (high.rolling(tenkan_period).max() + low.rolling(tenkan_period).min()) / 2
    kijun = (high.rolling(kijun_period).max() + low.rolling(kijun_period).min()) / 2

    senkou_a = ((tenkan + kijun) / 2).shift(displacement)
    senkou_b = ((high.rolling(senkou_b_period).max() + low.rolling(senkou_b_period).min()) / 2).shift(
        displacement
    )

    cloud_top = pd.concat([senkou_a, senkou_b], axis=1).max(axis=1)
    cloud_bottom = pd.concat([senkou_a, senkou_b], axis=1).min(axis=1)

    valid = cloud_top.notna() & cloud_bottom.notna()
    top_dist = (close - cloud_top).abs() / cloud_top * 100
    bottom_dist = (close - cloud_bottom).abs() / cloud_bottom * 100

    position = pd.Series([None] * len(close), index=close.index, dtype=object)

    is_top = valid & (top_dist <= tolerance_pct)
    is_bottom = valid & ~is_top & (bottom_dist <= tolerance_pct)
    is_inside = valid & ~is_top & ~is_bottom & (close >= cloud_bottom) & (close <= cloud_top)
    is_above = valid & ~is_top & ~is_bottom & ~is_inside & (close > cloud_top)
    is_below = valid & ~is_top & ~is_bottom & ~is_inside & ~is_above & (close < cloud_bottom)

    position[is_top] = "top"
    position[is_bottom] = "bottom"
    position[is_inside] = "inside"
    position[is_above] = "above"
    position[is_below] = "below"

    return position, cloud_top, cloud_bottom


def resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    """1시간봉 OHLC 데이터프레임을 4시간봉으로 리샘플링.
    (yfinance가 4h 인터벌을 직접 제공하지 않아서 60m 데이터를 묶어서 만듦)

    기준점(origin)을 자정이 아니라 데이터의 첫 시점(보통 장 시작 09:30 ET)에
    맞춤. 자정 기준으로 하면 정규장(09:30~16:00, 6.5시간)이 "9:30~12:00"
    (2.5시간짜리)과 "12:00~16:00"(마감 시간대를 포함한 온전한 4시간짜리)로
    불균등하게 갈려서, 거래량이 원래 몰리는 마감 시간대 봉이 길이까지 길어져
    거래량 급증이 구조적으로 과대평가되는 문제가 있었음. 장 시작 기준으로
    맞추면 "9:30~13:30"(4시간) / "13:30~16:00"(2.5시간)으로 나뉘어서
    매일 같은 패턴으로 일관되게 쪼개짐 (그래도 6.5시간이 4로 안 나눠떨어지는
    근본적 한계는 여전히 있어 완벽한 균등 분할은 아님).
    """
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in df.columns:
        agg["Volume"] = "sum"
    origin = df.index[0] if len(df) > 0 else "start_day"
    resampled = df.resample("4h", origin=origin).agg(agg)
    # 거래가 없던 구간(예: 야간)은 Close가 NaN으로 남음. Volume은 빈 구간도
    # sum() 결과가 0(NaN 아님)이라 dropna(how="all")로는 안 걸러지므로,
    # 실제 거래가 있었는지는 Close 기준으로 판단해서 제거함.
    resampled = resampled.dropna(subset=["Close"])
    return resampled
