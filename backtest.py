"""
backtest.py
지금 쓰고 있는 신호들(RSI 과매도/과매수, SMA120/200 터치, 일목균형표
터치, RSI 다이버전스, 골든크로스/데드크로스, 볼린저밴드 스퀴즈)이 과거에
실제로 얼마나 잘 맞았는지 검증하는 백테스트. 거래량 급증 여부도 각
이벤트에 같이 기록됨(참고용 부가정보).

참고: 일목구름대 "돌파"(상방/하방)는 백테스트 결과 승률이 가장 낮고
빈도가 가장 잦아서 실제 알림에서는 비활성화했지만(터치는 계속 사용),
비교 참고용으로 백테스트 통계에는 계속 포함되어 있음.

이 파일은 세 가지 방식으로 신호를 검증함:

  1) 고정 기간 수익률 (기존): "신호가 발생한 시점" 각각에 대해, 그
     이후 N거래일 뒤 가격이 얼마나 움직였는지(수익률, 승률)를 집계함.
     -> backtest_events.csv / backtest_summary.csv

  2) 손익비(목표가/손절가) 시뮬레이션: formatting.py의
     SIGNAL_DIRECTION에 매수/매도 방향이 정의된 신호(RSI 과매도/과매수
     진입, RSI 다이버전스, 골든/데드크로스, 볼린저 스퀴즈 해제)만 대상으로
     "다음날 시가에 진입해서, 손절 -stop_pct% / 목표 +stop_pct*rr%를
     실제로 걸어뒀다면 어느 쪽이 먼저 닿았을지"를 하루하루 시뮬레이션함.
     같은 날 목표/손절이 둘 다 닿으면 보수적으로 손절이 먼저 체결된 것으로
     처리하고, max_hold거래일 안에 아무것도 안 닿으면 그날 종가로 청산함.
     -> backtest_tpsl_events.csv / backtest_tpsl_summary.csv
     (방향성 없는 SMA/일목 터치, 볼린저 스퀴즈 진입 자체는 매수/매도 관점이
     없어서 이 시뮬레이션 대상에서 자동 제외됨 - 라이브 알림에서 "매수/매도
     관점"이 붙는 신호와 정확히 같은 기준을 재사용함)

  3) 물타기(추가매수) 시뮬레이션 (신규, --dca-max-adds>0일 때만): 2)와
     같은 진입 대상/시점을 쓰되, 손절 대신 "직전 체결가 대비
     dca_step_pct%만큼 더 불리해지면 추가매수"를 dca_multiplier배씩
     최대 dca_max_adds회까지 허용함. 목표가는 그때그때 갱신되는 평단가
     기준으로 다시 계산되고(그래서 물을 타면 같은 반등폭으로도 더 쉽게
     목표에 닿을 수 있음), 실탄을 다 쓰고 나서도 계속 불리해지면 마지막
     체결가 기준 -stop_pct%에서 최종 손절함.
     -> backtest_dca_events.csv / backtest_dca_summary.csv
     (2)의 결과와 나란히 비교해서 "물타기가 실제로 승률/손익을 개선하는지,
     대신 자본을 얼마나 더 많이 묶어두게 되는지"를 같이 봐야 함 - 물타기는
     반등에 필요한 %는 줄여주지만 반등 확률 자체를 높여주는 건 아니므로)

config.py에 있는 것과 정확히 같은 임계값(RSI 30/70, SMA ±1%, 일목
9/26/52, 다이버전스 룩백, SMA50/200 교차, 볼린저밴드 20/2 등)을 그대로
재사용함.

로컬에서 실행 (샌드박스는 금융 API 접근이 막혀있어서 여기선 못 돌림):
  pip install -r requirements.txt
  python refresh_cache.py          # 캐시된 유니버스 쓰려면 먼저 필요 (선택)
  python backtest.py                # 기본: 일봉, 캐시된 유니버스, 최근 5년, 손절3%/손익비1:2/최대20거래일
  python backtest.py --tickers AAPL,MSFT,TSLA,SOXL   # 특정 종목만 빠르게
  python backtest.py --years 3 --horizons 5,10,20     # 기간/평가시점 조절
  python backtest.py --stop-pct 4 --rr 2.5 --max-hold 15   # 손절4%/손익비1:2.5/최대15거래일로 시뮬레이션
  python backtest.py --entry-lag 0   # 신호 당일 종가 진입으로(비현실적 참고용) 비교하고 싶을 때
  python backtest.py --telegram                        # 결과 요약을 Telegram으로도 전송
  python backtest.py --timeframe 4h                     # 4시간봉 기준으로 검증 (라이브 intraday_monitor.py와 같은 로직)
  python backtest.py --timeframe 4h --years 2 --telegram  # 4h는 야후 60분봉 한계상 최대 730일(≈2년)까지만
  python backtest.py --dca-max-adds 3                     # 물타기(추가매수) 시뮬레이션도 같이 (기본: --stop-pct%마다, 최대3회)
  python backtest.py --dca-max-adds 3 --dca-step-pct 2 --dca-multiplier 1.5 --telegram   # 2%마다, 갈수록 강하게(1.5배씩) 최대3회

결과물 (--timeframe 4h로 돌리면 전부 _4h가 붙은 파일명으로 따로 저장되어
  일봉 결과와 안 섞임: backtest_events_4h.csv 등):
  backtest_events.csv        : 발생한 모든 신호 개별 이벤트 + 기간별 수익률
  backtest_summary.csv       : 신호별 집계 (발생횟수/평균수익률/승률)
  backtest_summary.png       : 신호별 승률 막대그래프 (matplotlib 있으면)
  backtest_tpsl_events.csv   : 방향성 신호별 손익비 시뮬레이션 개별 거래 기록
  backtest_tpsl_summary.csv  : 신호별 목표/손절 적중률 + 기대값(R) 집계
  backtest_dca_events.csv    : (--dca-max-adds>0일 때만) 물타기 시뮬레이션 개별 거래 기록
  backtest_dca_summary.csv   : (--dca-max-adds>0일 때만) 신호별 물타기 적중률 + 평균손익 집계
"""

import argparse

import numpy as np
import pandas as pd
import yfinance as yf

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
    DIVERGENCE_LOOKBACK,
    RSI_DIVERGENCE_ZONE_BUFFER,
    VOLUME_LOOKBACK,
    VOLUME_SPIKE_MULTIPLIER,
    SMA_CROSS_FAST,
    SMA_CROSS_SLOW,
    BB_PERIOD,
    BB_STD_MULTIPLIER,
    BB_SQUEEZE_LOOKBACK,
)
from indicators import wilder_rsi, detect_divergence, volume_spike_ratio, resample_to_4h
from formatting import SIGNAL_DIRECTION


def parse_args():
    p = argparse.ArgumentParser(description="신호별 과거 성과 백테스트")
    p.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="쉼표로 구분한 티커 목록 (생략하면 캐시된 스캔 유니버스 전체 사용)",
    )
    p.add_argument(
        "--timeframe",
        choices=["daily", "4h"],
        default="daily",
        help="일봉(daily, 기본) 또는 4시간봉(4h) 기준으로 검증할지. "
        "4h는 야후파이낸스 60분봉 제공 한계 때문에 최근 최대 730일(약 2년)치만 가능함 - "
        "라이브 4H 알림(intraday_monitor.py)과 완전히 같은 로직(SMA/RSI 등 '기간' 숫자를 "
        "4시간봉 개수로 그대로 재사용, 일봉보다 훨씬 짧은 호흡)으로 검증함.",
    )
    p.add_argument(
        "--years",
        type=int,
        default=5,
        help="과거 몇 년치로 검증할지 (기본 5, --timeframe 4h는 야후 제공 한계 때문에 자동으로 2년으로 상한)",
    )
    p.add_argument(
        "--horizons",
        type=str,
        default=None,
        help="진입 후 며칠(일봉) 또는 몇 개 4H봉(4h) 뒤 수익률을 볼지, 쉼표구분 "
        "(기본: daily=5,10,20거래일 / 4h=6,12,24봉)",
    )
    p.add_argument(
        "--telegram",
        action="store_true",
        help="백테스트 요약 결과를 Telegram으로도 전송 (config.py에 토큰/chat_id 설정되어 있어야 함)",
    )
    p.add_argument(
        "--stop-pct",
        type=float,
        default=3.0,
        help="손익비 시뮬레이션의 손절 폭 %% (기본 3.0). 목표폭은 stop-pct * rr로 자동 계산됨",
    )
    p.add_argument(
        "--rr",
        type=float,
        default=2.0,
        help="손익비 목표/손절 비율 (기본 2.0 = 손절1:목표2). 예: stop-pct=3, rr=2 -> 손절-3%%/목표+6%%",
    )
    p.add_argument(
        "--max-hold",
        type=int,
        default=20,
        help="목표/손절 시뮬레이션에서 최대 보유 기간 - 일봉이면 거래일 수, 4h면 4H봉 개수 (기본 20). "
        "이 안에 안 닿으면 종가 청산",
    )
    p.add_argument(
        "--entry-lag",
        type=int,
        default=1,
        help="신호 발생 시점으로부터 몇 칸(일봉=거래일 / 4h=4H봉) 뒤 시가에 진입할지 (기본 1 = 다음 칸 시가. "
        "신호는 해당 봉 종가 확정 후에야 알 수 있으므로 같은 봉 종가 진입은 비현실적)",
    )
    p.add_argument(
        "--dca-max-adds",
        type=int,
        default=0,
        help="물타기(추가매수) 시뮬레이션도 같이 돌릴지 - 최대 몇 번까지 추가매수 허용할지 (기본 0 = 물타기 시뮬레이션 안 함)",
    )
    p.add_argument(
        "--dca-step-pct",
        type=float,
        default=None,
        help="직전 체결가 대비 몇 %% 더 불리하게 움직이면 추가매수할지 (기본: --stop-pct와 동일한 값)",
    )
    p.add_argument(
        "--dca-multiplier",
        type=float,
        default=1.0,
        help="매 회차 추가매수 수량 배수 (기본 1.0 = 매번 동일 수량, 1.5 이상이면 갈수록 강하게 태우는 마틴게일 식)",
    )
    args = p.parse_args()
    if args.horizons is None:
        args.horizons = "6,12,24" if args.timeframe == "4h" else "5,10,20"
    if args.dca_step_pct is None:
        args.dca_step_pct = args.stop_pct
    return args


def get_tickers(arg_tickers):
    if arg_tickers:
        return [t.strip().upper() for t in arg_tickers.split(",")]
    try:
        from data import get_scan_universe

        tickers = get_scan_universe()
        if tickers:
            print(f"캐시된 스캔 유니버스 사용: {len(tickers)}개 종목")
            return tickers
    except Exception:
        pass
    print(
        "캐시된 유니버스가 없어서 기본 샘플 종목으로 진행합니다. "
        "(refresh_cache.py를 먼저 돌리면 실제 스캔 유니버스 전체로 백테스트 가능)"
    )
    return ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "JPM", "XOM", "SOXL", "NAIL", "TSLQ"]


def compute_signal_series(df: pd.DataFrame) -> pd.DataFrame:
    """일봉 OHLC 전체 기간에 대해, 매 시점의 신호 상태를 한 번에(벡터화) 계산.
    config.py의 실제 운영 임계값과 동일한 로직 (signals.py/indicators.py와 같은 기준)."""
    close, high, low = df["Close"], df["High"], df["Low"]

    rsi = wilder_rsi(close, RSI_PERIOD)
    rsi_zone = pd.Series("normal", index=close.index)
    rsi_zone[rsi <= RSI_THRESHOLD] = "oversold"
    rsi_zone[rsi >= RSI_OVERBOUGHT_THRESHOLD] = "overbought"

    out = pd.DataFrame(index=close.index)
    out["close"] = close
    out["rsi"] = rsi
    out["rsi_zone"] = rsi_zone

    for period in SMA_TOUCH_PERIODS:
        sma = close.rolling(period).mean()
        dist_pct = (close - sma).abs() / sma * 100
        out[f"sma{period}_touch"] = dist_pct <= SMA_TOUCH_TOLERANCE_PCT

    tenkan = (high.rolling(ICHIMOKU_TENKAN).max() + low.rolling(ICHIMOKU_TENKAN).min()) / 2
    kijun = (high.rolling(ICHIMOKU_KIJUN).max() + low.rolling(ICHIMOKU_KIJUN).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(ICHIMOKU_DISPLACEMENT)
    senkou_b = (
        (high.rolling(ICHIMOKU_SENKOU_B).max() + low.rolling(ICHIMOKU_SENKOU_B).min()) / 2
    ).shift(ICHIMOKU_DISPLACEMENT)

    cloud_top = pd.concat([senkou_a, senkou_b], axis=1).max(axis=1)
    cloud_bottom = pd.concat([senkou_a, senkou_b], axis=1).min(axis=1)

    top_dist = (close - cloud_top).abs() / cloud_top * 100
    bottom_dist = (close - cloud_bottom).abs() / cloud_bottom * 100

    position = pd.Series("inside", index=close.index)
    position[close > cloud_top] = "above"
    position[close < cloud_bottom] = "below"
    position[top_dist <= ICHIMOKU_TOUCH_TOLERANCE_PCT] = "top"
    position[bottom_dist <= ICHIMOKU_TOUCH_TOLERANCE_PCT] = "bottom"
    position[cloud_top.isna() | cloud_bottom.isna()] = np.nan  # 데이터 부족한 초반 구간 제외

    out["ichimoku_position"] = position

    # ---- RSI 다이버전스 (하루하루 인과적으로 계산 - 라이브와 동일한 detect_divergence 함수 재사용) ----
    divergence_kind = pd.Series([None] * len(close), index=close.index, dtype=object)
    for i in range(len(close)):
        kind, _ = detect_divergence(
            close.iloc[: i + 1],
            rsi.iloc[: i + 1],
            DIVERGENCE_LOOKBACK,
            RSI_THRESHOLD,
            RSI_OVERBOUGHT_THRESHOLD,
            RSI_DIVERGENCE_ZONE_BUFFER,
        )
        divergence_kind.iloc[i] = kind
    out["divergence_kind"] = divergence_kind

    # ---- 거래량 급증 (Volume 컬럼 있을 때만) ----
    if "Volume" in df.columns:
        volume = df["Volume"]
        vol_ratio = pd.Series(np.nan, index=close.index)
        for i in range(len(close)):
            vr = volume_spike_ratio(volume.iloc[: i + 1], VOLUME_LOOKBACK)
            if vr is not None:
                vol_ratio.iloc[i] = vr
        out["volume_ratio"] = vol_ratio
        out["is_volume_spike"] = vol_ratio >= VOLUME_SPIKE_MULTIPLIER
    else:
        out["volume_ratio"] = np.nan
        out["is_volume_spike"] = False

    # ---- 골든크로스/데드크로스 (SMA50 vs SMA200 위치) ----
    fast_sma = close.rolling(SMA_CROSS_FAST).mean()
    slow_sma = close.rolling(SMA_CROSS_SLOW).mean()
    cross_position = pd.Series(np.nan, index=close.index, dtype=object)
    cross_position[fast_sma > slow_sma] = "above"
    cross_position[fast_sma <= slow_sma] = "below"
    out["sma_cross_position"] = cross_position

    # ---- 볼린저 밴드 스퀴즈 ----
    bb_middle = close.rolling(BB_PERIOD).mean()
    bb_std = close.rolling(BB_PERIOD).std()
    bb_upper = bb_middle + BB_STD_MULTIPLIER * bb_std
    bb_lower = bb_middle - BB_STD_MULTIPLIER * bb_std
    bandwidth = (bb_upper - bb_lower) / bb_middle
    squeeze_cutoff = bandwidth.rolling(BB_SQUEEZE_LOOKBACK).quantile(0.10)
    out["bb_is_squeeze"] = bandwidth <= squeeze_cutoff
    out["bb_upper"] = bb_upper
    out["bb_lower"] = bb_lower

    breakout_dir = pd.Series(None, index=close.index, dtype=object)
    breakout_dir[close > bb_upper] = "up"
    breakout_dir[close < bb_lower] = "down"
    out["bb_breakout_dir"] = breakout_dir

    return out


def detect_entries(sig: pd.DataFrame) -> pd.DataFrame:
    """각 신호별로 '새로 진입한'(직전엔 아니었다가 이번에 조건 충족) 시점만 이벤트로 추출.
    (계속 유지되는 동안 매일 잡히지 않도록 - 실제 운영 로직인 상태전이 감지와 동일한 개념)"""
    events = []

    def add_events(mask: pd.Series, signal_type: str):
        entries = mask.fillna(False) & ~mask.fillna(False).shift(1, fill_value=False)
        for date in sig.index[entries]:
            has_vol_col = "is_volume_spike" in sig.columns
            events.append(
                {
                    "date": date,
                    "signal_type": signal_type,
                    "entry_close": sig.loc[date, "close"],
                    "volume_spike": bool(sig.loc[date, "is_volume_spike"]) if has_vol_col else False,
                }
            )

    add_events(sig["rsi_zone"] == "oversold", "RSI 과매도 진입")
    add_events(sig["rsi_zone"] == "overbought", "RSI 과매수 진입")
    for period in SMA_TOUCH_PERIODS:
        add_events(sig[f"sma{period}_touch"], f"SMA{period} 터치")
    add_events(sig["ichimoku_position"] == "top", "일목구름대 상단 터치")
    add_events(sig["ichimoku_position"] == "bottom", "일목구름대 하단 터치")
    add_events(sig["ichimoku_position"] == "above", "일목구름대 상방 돌파")
    add_events(sig["ichimoku_position"] == "below", "일목구름대 하방 돌파")
    add_events(sig["divergence_kind"] == "bullish", "RSI 강세 다이버전스")
    add_events(sig["divergence_kind"] == "bearish", "RSI 약세 다이버전스")

    add_events(sig["sma_cross_position"] == "above", "골든크로스 발생")
    add_events(sig["sma_cross_position"] == "below", "데드크로스 발생")

    add_events(sig["bb_is_squeeze"] == True, "볼린저밴드 스퀴즈 진입")  # noqa: E712

    squeeze_release = (~sig["bb_is_squeeze"].fillna(False)) & (sig["bb_is_squeeze"].shift(1).fillna(False))
    add_events(squeeze_release & (sig["bb_breakout_dir"] == "up"), "볼린저밴드 스퀴즈 해제(상방)")
    add_events(squeeze_release & (sig["bb_breakout_dir"] == "down"), "볼린저밴드 스퀴즈 해제(하방)")

    return pd.DataFrame(events)


def add_forward_returns(events: pd.DataFrame, sig: pd.DataFrame, horizons: list) -> pd.DataFrame:
    close = sig["close"]
    dates = list(sig.index)
    date_to_idx = {d: i for i, d in enumerate(dates)}

    for h in horizons:
        col = f"return_{h}d"
        values = []
        for _, row in events.iterrows():
            idx = date_to_idx.get(row["date"])
            if idx is None or idx + h >= len(dates):
                values.append(np.nan)
                continue
            future_close = close.iloc[idx + h]
            values.append(round((future_close - row["entry_close"]) / row["entry_close"] * 100, 2))
        events[col] = values

    return events


def build_ticker_frames(tickers: list, timeframe: str, years: int):
    """timeframe("daily"|"4h")에 맞게 배치 다운로드하고, 종목별 OHLCV df를
    돌려주는 콜러블(get_df)을 반환. 4h는 야후파이낸스 60분봉 제공 한계
    (최대 730일) 때문에 요청한 years와 무관하게 최근 730일로 자동 상한됨.

    반환: (get_df: ticker -> DataFrame|None, lookback_desc: str)
    """
    if timeframe == "daily":
        data = yf.download(
            tickers, period=f"{years}y", interval="1d", group_by="ticker",
            auto_adjust=True, threads=True, progress=False,
        )

        def get_df(ticker):
            try:
                df = data[ticker] if isinstance(data.columns, pd.MultiIndex) else data
                cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
                return df[cols].dropna(how="all")
            except Exception:
                return None

        return get_df, f"최근 {years}년(일봉)"

    # ---- 4h ----
    eff_days = min(years * 365, 730)
    if years * 365 > 730:
        print(
            f"(참고: 4시간봉은 야후파이낸스 60분봉 제공 한계 때문에 최대 730일까지만 조회 가능해서, "
            f"요청하신 {years}년 대신 최근 {eff_days}일로 자동 조정합니다)"
        )
    data = yf.download(
        tickers, period=f"{eff_days}d", interval="60m", group_by="ticker",
        auto_adjust=True, threads=True, progress=False, prepost=True,
    )

    def get_df(ticker):
        try:
            hourly = data[ticker] if isinstance(data.columns, pd.MultiIndex) else data
            cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in hourly.columns]
            hourly = hourly[cols].dropna(how="all")
            if hourly.empty:
                return None
            return resample_to_4h(hourly)
        except Exception:
            return None

    return get_df, f"최근 {eff_days}일(4시간봉)"


HORIZON_LABELS = {5: "1주", 10: "2주", 15: "3주", 20: "1개월", 40: "2개월", 60: "3개월"}
HORIZON_LABELS_4H = {6: "~1.5일", 12: "~3일", 24: "~1주"}  # 대략치 (하루 4H봉 개수가 프리/애프터마켓 포함 균등하지 않아 참고용)


def simulate_tp_sl(
    events: pd.DataFrame, df: pd.DataFrame, stop_pct: float, rr_ratio: float, max_hold: int, entry_lag: int = 1
) -> pd.DataFrame:
    """방향성 있는 신호(formatting.SIGNAL_DIRECTION에 정의된 매수/매도 관점
    신호)만 대상으로, 실제로 목표가/손절가를 걸어뒀다면 어떻게 됐을지
    거래일 단위로 시뮬레이션.

    - 진입: 신호 발생일 + entry_lag거래일 뒤 시가 (기본 1 = 다음날 시가)
    - 손절폭 stop_pct(%) / 목표폭 stop_pct*rr_ratio(%)
    - 매일 High/Low를 확인해서 목표/손절 중 먼저 닿은 쪽으로 청산.
      같은 날 둘 다 닿으면 보수적으로 손절이 먼저 체결된 것으로 처리
    - max_hold거래일 안에 아무것도 안 닿으면 그날 종가로 청산(time_exit)
    - r_multiple: 손절폭을 1R로 뒀을 때 실제 손익이 몇 R이었는지
      (target 적중 시 +rr_ratio, stop 적중 시 -1, time_exit은 그 사이 값)
    """
    if events.empty:
        return pd.DataFrame()

    dates = list(df.index)
    date_to_idx = {d: i for i, d in enumerate(dates)}
    opens, highs, lows, closes = df["Open"], df["High"], df["Low"], df["Close"]

    rows = []
    for _, ev in events.iterrows():
        direction = SIGNAL_DIRECTION.get(ev["signal_type"])
        if not direction:
            continue  # SMA/일목 터치, 볼린저 스퀴즈 진입 등 방향성 없는 신호는 대상 제외
        sig_idx = date_to_idx.get(ev["date"])
        if sig_idx is None:
            continue
        entry_idx = sig_idx + entry_lag
        if entry_idx >= len(dates):
            continue
        entry_price = opens.iloc[entry_idx]
        if pd.isna(entry_price) or entry_price <= 0:
            continue

        if direction == "bullish":
            stop_price = entry_price * (1 - stop_pct / 100)
            target_price = entry_price * (1 + stop_pct * rr_ratio / 100)
        else:
            stop_price = entry_price * (1 + stop_pct / 100)
            target_price = entry_price * (1 - stop_pct * rr_ratio / 100)

        outcome = "time_exit"
        exit_idx = min(entry_idx + max_hold, len(dates) - 1)
        exit_price = closes.iloc[exit_idx]

        for i in range(entry_idx, min(entry_idx + max_hold, len(dates) - 1) + 1):
            hi, lo = highs.iloc[i], lows.iloc[i]
            if direction == "bullish":
                hit_stop = lo <= stop_price
                hit_target = hi >= target_price
            else:
                hit_stop = hi >= stop_price
                hit_target = lo <= target_price
            if hit_stop:  # 같은 날 목표도 같이 닿았어도 보수적으로 손절 우선 처리
                outcome, exit_price, exit_idx = "stop", stop_price, i
                break
            if hit_target:
                outcome, exit_price, exit_idx = "target", target_price, i
                break

        r_multiple = (
            (exit_price - entry_price) / (entry_price - stop_price)
            if direction == "bullish"
            else (entry_price - exit_price) / (stop_price - entry_price)
        )
        rows.append(
            {
                "ticker": ev.get("ticker"),
                "signal_type": ev["signal_type"],
                "direction": direction,
                "signal_date": ev["date"],
                "entry_date": dates[entry_idx],
                "entry_price": round(entry_price, 2),
                "stop_price": round(stop_price, 2),
                "target_price": round(target_price, 2),
                "outcome": outcome,
                "exit_date": dates[exit_idx],
                "exit_price": round(exit_price, 2),
                "days_held": exit_idx - entry_idx,
                "r_multiple": round(r_multiple, 2),
            }
        )

    return pd.DataFrame(rows)


def summarize_tp_sl(tpsl_df: pd.DataFrame) -> pd.DataFrame:
    """신호별로 목표/손절 적중 횟수, 승률(시간청산 제외), 평균 보유일,
    기대값(전체 거래 평균 R)을 집계."""
    rows = []
    for signal_type, g in tpsl_df.groupby("signal_type"):
        decided = g[g["outcome"].isin(["target", "stop"])]
        n_decided = len(decided)
        n_target = int((decided["outcome"] == "target").sum())
        n_stop = int((decided["outcome"] == "stop").sum())
        n_time = int((g["outcome"] == "time_exit").sum())
        rows.append(
            {
                "signal_type": signal_type,
                "count": len(g),
                "target_hit": n_target,
                "stop_hit": n_stop,
                "time_exit": n_time,
                "win_rate_excl_timeexit(%)": round(n_target / n_decided * 100, 1) if n_decided else None,
                "avg_days_held": round(g["days_held"].mean(), 1),
                "expectancy(R)": round(g["r_multiple"].mean(), 3),
            }
        )
    return pd.DataFrame(rows).sort_values("count", ascending=False)


def simulate_dca(
    events: pd.DataFrame,
    df: pd.DataFrame,
    stop_pct: float,
    rr_ratio: float,
    dca_step_pct: float,
    dca_max_adds: int,
    dca_multiplier: float,
    max_hold: int,
    entry_lag: int = 1,
) -> pd.DataFrame:
    """simulate_tp_sl과 진입 시점/대상 신호는 완전히 같지만, 손절가에
    도달하는 대신 "일정 % 더 빠질 때마다 추가 매수(물타기)"를 최대
    dca_max_adds번까지 허용하고, 그때그때 평단가 기준으로 목표가를
    다시 계산하는 시뮬레이션. 진짜 손절(하드 스탑)은 "추가 매수 다
    써버린 뒤에도" 마지막 체결가 기준 stop_pct%만큼 더 빠지면 발동함
    (물 탈 실탄이 남아있는 동안은 손절 안 함 - 실제 물타기 매매의 의도와
    동일하게 재현).

    - dca_step_pct: 직전 체결가(최초 진입가 또는 마지막 추가매수가) 대비
      몇 % 더 불리하게 움직이면 추가매수할지
    - dca_multiplier: 매 회차 추가매수 수량이 직전 대비 몇 배인지
      (1.0=매번 동일 수량, 1.5 이상=갈수록 강하게 태우는 마틴게일 식)
    - 같은 봉 안에서 목표/추가매수가 동시에 조건을 만족하면 "목표 먼저"로
      보수적으로 처리(추가매수 조건 확인 전에 그 봉에서 이미 익절하고
      끝난 것으로 침). 하드 스탑은 실탄이 없을 때만 확인함.
    - r_multiple 대신 avg_cost(평단가) 기준 실현 손익률(pnl_pct)로 집계함 -
      물타기는 회차마다 실제로 투입되는 자본(총 유닛 수)이 달라져서, 손절
      1회 폭을 "1R"로 고정하는 기존 R-멀티플 정의가 그대로는 안 맞기 때문.
    """
    if events.empty or dca_max_adds <= 0:
        return pd.DataFrame()

    dates = list(df.index)
    date_to_idx = {d: i for i, d in enumerate(dates)}
    opens, highs, lows, closes = df["Open"], df["High"], df["Low"], df["Close"]

    rows = []
    for _, ev in events.iterrows():
        direction = SIGNAL_DIRECTION.get(ev["signal_type"])
        if not direction:
            continue
        sig_idx = date_to_idx.get(ev["date"])
        if sig_idx is None:
            continue
        entry_idx = sig_idx + entry_lag
        if entry_idx >= len(dates):
            continue
        entry_price = opens.iloc[entry_idx]
        if pd.isna(entry_price) or entry_price <= 0:
            continue

        bullish = direction == "bullish"
        last_fill_price = entry_price
        total_units = 1.0
        total_cost = entry_price * 1.0
        adds_used = 0
        outcome = "time_exit"
        exit_idx = min(entry_idx + max_hold, len(dates) - 1)
        exit_price = closes.iloc[exit_idx]

        for i in range(entry_idx, min(entry_idx + max_hold, len(dates) - 1) + 1):
            avg_cost = total_cost / total_units
            hi, lo = highs.iloc[i], lows.iloc[i]

            target_price = avg_cost * (1 + rr_ratio * stop_pct / 100) if bullish else avg_cost * (1 - rr_ratio * stop_pct / 100)
            hit_target = hi >= target_price if bullish else lo <= target_price
            if hit_target:
                outcome, exit_price, exit_idx = "target", target_price, i
                break

            if adds_used >= dca_max_adds:
                # 실탄 소진 - 마지막 체결가 기준 최종 하드 스탑만 확인
                stop_price = last_fill_price * (1 - stop_pct / 100) if bullish else last_fill_price * (1 + stop_pct / 100)
                hit_stop = lo <= stop_price if bullish else hi >= stop_price
                if hit_stop:
                    outcome, exit_price, exit_idx = "stop", stop_price, i
                    break
                continue

            add_trigger_price = (
                last_fill_price * (1 - dca_step_pct / 100) if bullish else last_fill_price * (1 + dca_step_pct / 100)
            )
            hit_add = lo <= add_trigger_price if bullish else hi >= add_trigger_price
            if hit_add:
                adds_used += 1
                add_size = dca_multiplier ** adds_used
                total_units += add_size
                total_cost += add_trigger_price * add_size
                last_fill_price = add_trigger_price

        avg_cost = total_cost / total_units
        pnl_pct = (exit_price - avg_cost) / avg_cost * 100 if bullish else (avg_cost - exit_price) / avg_cost * 100

        rows.append(
            {
                "ticker": ev.get("ticker"),
                "signal_type": ev["signal_type"],
                "direction": direction,
                "signal_date": ev["date"],
                "entry_date": dates[entry_idx],
                "entry_price": round(entry_price, 2),
                "adds_used": adds_used,
                "total_units": round(total_units, 3),
                "avg_cost": round(avg_cost, 2),
                "outcome": outcome,
                "exit_date": dates[exit_idx],
                "exit_price": round(exit_price, 2),
                "days_held": exit_idx - entry_idx,
                "pnl_pct": round(pnl_pct, 2),
            }
        )

    return pd.DataFrame(rows)


def summarize_dca(dca_df: pd.DataFrame) -> pd.DataFrame:
    """신호별로 목표/손절 적중 횟수, 승률(시간청산 제외), 평균 추가매수
    횟수·투입자본배수, 평균 실현손익률(%)을 집계."""
    rows = []
    for signal_type, g in dca_df.groupby("signal_type"):
        decided = g[g["outcome"].isin(["target", "stop"])]
        n_decided = len(decided)
        n_target = int((decided["outcome"] == "target").sum())
        n_stop = int((decided["outcome"] == "stop").sum())
        n_time = int((g["outcome"] == "time_exit").sum())
        rows.append(
            {
                "signal_type": signal_type,
                "count": len(g),
                "target_hit": n_target,
                "stop_hit": n_stop,
                "time_exit": n_time,
                "win_rate_excl_timeexit(%)": round(n_target / n_decided * 100, 1) if n_decided else None,
                "avg_adds_used": round(g["adds_used"].mean(), 2),
                "avg_total_units": round(g["total_units"].mean(), 2),
                "avg_days_held": round(g["days_held"].mean(), 1),
                "avg_pnl(%)": round(g["pnl_pct"].mean(), 3),
            }
        )
    return pd.DataFrame(rows).sort_values("count", ascending=False)


def build_tpsl_telegram_summary(
    tpsl_summary: pd.DataFrame, stop_pct: float, rr_ratio: float, max_hold: int, timeframe: str = "daily"
) -> str:
    target_pct = stop_pct * rr_ratio
    unit = "봉" if timeframe == "4h" else "거래일"
    tf_label = "4시간봉" if timeframe == "4h" else "일봉"
    lines = [
        f"🎯 [손익비 시뮬 · {tf_label}] 손절 -{stop_pct:g}% / 목표 +{target_pct:g}% (1:{rr_ratio:g}) · 최대보유 {max_hold}{unit}",
        "",
    ]
    for _, row in tpsl_summary.iterrows():
        win = row["win_rate_excl_timeexit(%)"]
        win_str = f"{win:.0f}%" if pd.notna(win) else "N/A"
        lines.append(
            f"· {row['signal_type']}: {int(row['count'])}건 | 목표{int(row['target_hit'])}·손절{int(row['stop_hit'])}"
            f"·시간청산{int(row['time_exit'])} | 승률(결판난 거래 기준) {win_str} | 기대값 {row['expectancy(R)']:+.2f}R"
            f" | 평균보유 {row['avg_days_held']:.1f}{unit}"
        )
    lines.append("")
    lines.append("(expectancy(R)이 양수여야 이 신호를 이 손익비대로 장기 반복했을 때 기대이익이 남는다는 뜻)")
    return "\n".join(lines)


def build_dca_telegram_summary(
    dca_summary: pd.DataFrame, stop_pct: float, rr_ratio: float, dca_step_pct: float,
    dca_max_adds: int, dca_multiplier: float, max_hold: int, timeframe: str = "daily",
) -> str:
    unit = "봉" if timeframe == "4h" else "거래일"
    tf_label = "4시간봉" if timeframe == "4h" else "일봉"
    lines = [
        f"🌊 [물타기 시뮬 · {tf_label}] {dca_step_pct:g}%마다 최대 {dca_max_adds}회 추가매수(배수 {dca_multiplier:g}) "
        f"· 실탄 소진 후 최종손절 -{stop_pct:g}% · 목표는 그때그때 평단 기준 +{stop_pct * rr_ratio:g}%(1:{rr_ratio:g}) "
        f"· 최대보유 {max_hold}{unit}",
        "",
    ]
    for _, row in dca_summary.iterrows():
        win = row["win_rate_excl_timeexit(%)"]
        win_str = f"{win:.0f}%" if pd.notna(win) else "N/A"
        lines.append(
            f"· {row['signal_type']}: {int(row['count'])}건 | 목표{int(row['target_hit'])}·손절{int(row['stop_hit'])}"
            f"·시간청산{int(row['time_exit'])} | 승률(결판난 거래 기준) {win_str} | 평균손익 {row['avg_pnl(%)']:+.2f}% "
            f"| 평균 추가매수 {row['avg_adds_used']:.1f}회(투입자본 평균 {row['avg_total_units']:.1f}배) "
            f"| 평균보유 {row['avg_days_held']:.1f}{unit}"
        )
    lines.append("")
    lines.append(
        "(같은 조건 '물타기 안 함' 버전은 바로 위 🎯 [손익비 시뮬] 메시지 참고 - 승률/평균손익을 나란히 비교해볼 것. "
        "투입자본 평균이 1보다 훨씬 크면, 그만큼 실제로 더 많은 돈을 걸어야 저 승률이 나온다는 뜻)"
    )
    return "\n".join(lines)


def _horizon_label(h: int, timeframe: str = "daily") -> str:
    labels = HORIZON_LABELS_4H if timeframe == "4h" else HORIZON_LABELS
    unit = "봉" if timeframe == "4h" else "거래일"
    friendly = labels.get(h)
    return f"{h}{unit}({friendly})" if friendly else f"{h}{unit}"


def build_telegram_summary(
    summary_df: pd.DataFrame, events_df: pd.DataFrame, tickers: list, lookback_desc: str,
    horizons: list, timeframe: str = "daily",
) -> str:
    """백테스트 요약을 Telegram 메시지 형태로 변환.
    실제 라이브 알림과 같은 신호명을 그대로 써서, "이 신호가 실제로 이렇게
    잘 작동하는지" 텔레그램에서 바로 확인할 수 있게 함.

    horizons에 넘긴 기간들을 전부(예: [10, 20] = 2주/1개월) 한 줄에 같이 보여줌."""
    tf_label = "4시간봉" if timeframe == "4h" else "일봉"
    lines = [
        f"🧪 [백테스트 · {tf_label}] {lookback_desc}, {len(tickers)}개 종목",
        f"(기준: {', '.join(_horizon_label(h, timeframe) for h in horizons)} 뒤 수익률, 전체는 backtest_summary.csv 참고)",
        "",
    ]

    for _, row in summary_df.iterrows():
        signal_type = row["signal_type"]
        count = int(row["count"])
        parts = []
        for h in horizons:
            avg_col = f"avg_return_{h}d(%)"
            win_col = f"win_rate_{h}d(%)"
            if avg_col in row and pd.notna(row[avg_col]):
                friendly = (HORIZON_LABELS_4H if timeframe == "4h" else HORIZON_LABELS).get(h, f"{h}")
                parts.append(f"{friendly} {row[avg_col]:+.2f}%(승률{row[win_col]:.0f}%)")
        if parts:
            lines.append(f"· {signal_type}: {count}건 | " + " | ".join(parts))
        else:
            lines.append(f"· {signal_type}: {count}건 (표본 부족으로 수익률 통계 없음)")

    # 실제 신호가 맞는지 눈으로 대조해볼 수 있게, 신호별 가장 최근 사례 1건씩 첨부
    lines.append("")
    lines.append("최근 발생 사례 (실제 차트와 대조용):")
    latest_per_signal = events_df.sort_values("date").groupby("signal_type").tail(1)
    for _, row in latest_per_signal.sort_values("date", ascending=False).iterrows():
        date_str = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
        lines.append(f"· {row['ticker']} {row['signal_type']} ({date_str}, 종가 ${row['entry_close']})")

    return "\n".join(lines)


def main():
    args = parse_args()
    tickers = get_tickers(args.tickers)
    horizons = [int(h) for h in args.horizons.split(",")]
    unit = "봉" if args.timeframe == "4h" else "거래일"
    suffix = "_4h" if args.timeframe == "4h" else ""

    get_df, lookback_desc = build_ticker_frames(tickers, args.timeframe, args.years)

    print(
        f"백테스트 대상: {len(tickers)}개 종목, {lookback_desc}, "
        f"진입 후 {horizons}{unit} 뒤 수익률 검증"
    )

    all_events = []
    all_tpsl = []
    all_dca = []
    skipped = 0
    for ticker in tickers:
        df = get_df(ticker)
        if df is None or df.empty or len(df) < 250:
            skipped += 1
            continue

        sig = compute_signal_series(df)
        events = detect_entries(sig)
        if events.empty:
            continue
        events = add_forward_returns(events, sig, horizons)
        events.insert(0, "ticker", ticker)
        all_events.append(events)

        tpsl = simulate_tp_sl(events, df, args.stop_pct, args.rr, args.max_hold, args.entry_lag)
        if not tpsl.empty:
            all_tpsl.append(tpsl)

        if args.dca_max_adds > 0:
            dca = simulate_dca(
                events, df, args.stop_pct, args.rr, args.dca_step_pct,
                args.dca_max_adds, args.dca_multiplier, args.max_hold, args.entry_lag,
            )
            if not dca.empty:
                all_dca.append(dca)

    if skipped:
        print(f"(데이터 부족/조회 실패로 {skipped}개 종목 제외)")

    if not all_events:
        print("발생한 신호가 하나도 없습니다.")
        return

    events_df = pd.concat(all_events, ignore_index=True)
    events_path = f"backtest_events{suffix}.csv"
    events_df.to_csv(events_path, index=False, encoding="utf-8-sig")
    print(f"\n개별 이벤트 {len(events_df)}건 -> {events_path} 저장")

    summary_rows = []
    for signal_type, group in events_df.groupby("signal_type"):
        row = {"signal_type": signal_type, "count": len(group)}
        for h in horizons:
            col = f"return_{h}d"
            valid = group[col].dropna()
            if len(valid) == 0:
                continue
            row[f"avg_return_{h}d(%)"] = round(valid.mean(), 2)
            row[f"median_return_{h}d(%)"] = round(valid.median(), 2)
            row[f"win_rate_{h}d(%)"] = round((valid > 0).mean() * 100, 1)
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows).sort_values("count", ascending=False)
    summary_path = f"backtest_summary{suffix}.csv"
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print("\n=== 신호별 요약 ===")
    print(summary_df.to_string(index=False))
    print(
        "\n(win_rate = 그 기간 뒤 수익률이 +였던 비율. RSI 과매수/일목 하방 돌파처럼\n"
        " '하락 방향'을 노리는 신호는 오히려 마이너스 수익률이 신호가 잘 맞은\n"
        " 케이스일 수 있으니, 신호 성격에 맞춰 방향 감안해서 해석할 것."
        + (f" · '{unit}'은 4시간봉 개수 기준(하루 개수가 균등하지 않아 참고용)" if args.timeframe == "4h" else "")
        + ")"
    )

    tpsl_summary = pd.DataFrame()
    if all_tpsl:
        tpsl_df = pd.concat(all_tpsl, ignore_index=True)
        tpsl_events_path = f"backtest_tpsl_events{suffix}.csv"
        tpsl_df.to_csv(tpsl_events_path, index=False, encoding="utf-8-sig")
        tpsl_summary = summarize_tp_sl(tpsl_df)
        tpsl_summary_path = f"backtest_tpsl_summary{suffix}.csv"
        tpsl_summary.to_csv(tpsl_summary_path, index=False, encoding="utf-8-sig")

        target_pct = args.stop_pct * args.rr
        print(
            f"\n=== 손익비 시뮬레이션 [{'4시간봉' if args.timeframe == '4h' else '일봉'}] "
            f"(손절 -{args.stop_pct:g}% / 목표 +{target_pct:g}% "
            f"= 1:{args.rr:g} · 최대보유 {args.max_hold}{unit} · 진입 {args.entry_lag}{unit} 후 시가) ==="
        )
        print(tpsl_summary.to_string(index=False))
        print(
            "\n(target_hit=목표가 먼저 도달, stop_hit=손절가 먼저 도달, time_exit=둘 다 못 닿아서 종가 청산\n"
            " · win_rate는 time_exit 제외 target/stop 결판난 거래만 기준 · expectancy(R)은 시간청산 포함\n"
            " 전체 거래의 평균 손익배수(1R=손절폭) - 이게 양수여야 이 손익비대로 장기 반복했을 때\n"
            " 기대이익이 남는다는 뜻. 방향성 없는 SMA/일목 터치, 볼린저 스퀴즈 진입은 매수/매도 관점이\n"
            " 없어서 이 표에서 자동 제외됨)"
        )
    else:
        print("\n(방향성 있는 신호(매수/매도 관점) 이벤트가 없어서 손익비 시뮬레이션 결과 없음)")

    dca_summary = pd.DataFrame()
    if args.dca_max_adds > 0:
        if all_dca:
            dca_df = pd.concat(all_dca, ignore_index=True)
            dca_events_path = f"backtest_dca_events{suffix}.csv"
            dca_df.to_csv(dca_events_path, index=False, encoding="utf-8-sig")
            dca_summary = summarize_dca(dca_df)
            dca_summary_path = f"backtest_dca_summary{suffix}.csv"
            dca_summary.to_csv(dca_summary_path, index=False, encoding="utf-8-sig")

            print(
                f"\n=== 물타기 시뮬레이션 [{'4시간봉' if args.timeframe == '4h' else '일봉'}] "
                f"({args.dca_step_pct:g}%마다 최대 {args.dca_max_adds}회 추가매수, 배수 {args.dca_multiplier:g} · "
                f"실탄 소진 후 최종손절 -{args.stop_pct:g}% · 목표는 그때그때 평단 기준 +{args.stop_pct * args.rr:g}%) ==="
            )
            print(dca_summary.to_string(index=False))
            print(
                "\n(avg_pnl(%)은 물타기까지 반영한 평단가 기준 실현 손익률 평균 - 바로 위 손익비 시뮬레이션의\n"
                " expectancy(R)이랑 나란히 비교해볼 것 · avg_total_units가 1보다 훨씬 크면 그만큼 더 많은\n"
                " 자본을 실제로 걸어야 저 승률/손익이 나온다는 뜻이라, 승률만 보고 좋다고 판단하면 안 됨)"
            )
        else:
            print("\n(물타기 시뮬레이션 대상 거래가 없습니다)")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # 한글(신호명)이 깨지지 않도록 시스템에 있는 한글 폰트를 찾아서 사용.
        # Windows는 보통 '맑은 고딕(Malgun Gothic)'이 기본 내장되어 있음.
        import matplotlib.font_manager as fm

        korean_font_candidates = ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"]
        available_fonts = {f.name for f in fm.fontManager.ttflist}
        chosen_font = next((f for f in korean_font_candidates if f in available_fonts), None)
        if chosen_font:
            matplotlib.rcParams["font.family"] = chosen_font
        matplotlib.rcParams["axes.unicode_minus"] = False  # 한글 폰트 쓸 때 마이너스 기호 깨짐 방지

        h = horizons[0]
        col = f"win_rate_{h}d(%)"
        if col in summary_df.columns:
            plot_df = summary_df.dropna(subset=[col])
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.barh(plot_df["signal_type"], plot_df[col])
            ax.set_xlabel(f"{h}{unit} 뒤 상승 비율 (%)")
            ax.set_title(f"신호별 승률 [{'4시간봉' if args.timeframe == '4h' else '일봉'}]")
            ax.axvline(50, color="gray", linestyle="--", linewidth=1)
            plt.tight_layout()
            chart_path = f"backtest_summary{suffix}.png"
            plt.savefig(chart_path, dpi=150)
            if chosen_font:
                print(f"차트 -> {chart_path} 저장")
            else:
                print(
                    f"차트 -> {chart_path} 저장 (한글 폰트를 못 찾아서 신호명이 "
                    "깨져 보일 수 있음 - '맑은 고딕' 등 한글 폰트 설치 후 다시 실행하면 해결됨)"
                )
    except ImportError:
        print("\n(matplotlib 없어서 차트는 생략함: pip install matplotlib 하면 다음번엔 생성됨)")

    if args.telegram:
        from notifier import send_telegram

        msg = build_telegram_summary(summary_df, events_df, tickers, lookback_desc, horizons, args.timeframe)
        send_telegram(msg)
        if not tpsl_summary.empty:
            tpsl_msg = build_tpsl_telegram_summary(
                tpsl_summary, args.stop_pct, args.rr, args.max_hold, args.timeframe
            )
            send_telegram(tpsl_msg)
        if not dca_summary.empty:
            dca_msg = build_dca_telegram_summary(
                dca_summary, args.stop_pct, args.rr, args.dca_step_pct,
                args.dca_max_adds, args.dca_multiplier, args.max_hold, args.timeframe,
            )
            send_telegram(dca_msg)
        print("\nTelegram으로 요약 전송함 (안 오면 config.py의 토큰/chat_id 확인, 또는 로컬에서 직접 값 채워서 테스트)")


if __name__ == "__main__":
    main()
