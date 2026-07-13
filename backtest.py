"""
backtest.py
지금 쓰고 있는 신호들(RSI 과매도/과매수, SMA120/200 터치, 일목균형표
터치/돌파, RSI 다이버전스)이 과거에 실제로 얼마나 잘 맞았는지 검증하는
백테스트. 거래량 급증 여부도 각 이벤트에 같이 기록됨(참고용 부가정보).

"신호가 발생한 시점" 각각에 대해, 그 이후 N거래일 뒤 가격이 얼마나
움직였는지(수익률, 승률)를 집계함. config.py에 있는 것과 정확히 같은
임계값(RSI 30/70, SMA ±1%, 일목 9/26/52, 다이버전스 룩백 등)을 그대로 재사용함.

로컬에서 실행 (샌드박스는 금융 API 접근이 막혀있어서 여기선 못 돌림):
  pip install -r requirements.txt
  python refresh_cache.py          # 캐시된 유니버스 쓰려면 먼저 필요 (선택)
  python backtest.py                # 기본: 캐시된 유니버스, 최근 5년
  python backtest.py --tickers AAPL,MSFT,TSLA,SOXL   # 특정 종목만 빠르게
  python backtest.py --years 3 --horizons 5,10,20     # 기간/평가시점 조절
  python backtest.py --telegram                        # 결과 요약을 Telegram으로도 전송

결과물:
  backtest_events.csv   : 발생한 모든 신호 개별 이벤트 + 기간별 수익률
  backtest_summary.csv  : 신호별 집계 (발생횟수/평균수익률/승률)
  backtest_summary.png  : 신호별 승률 막대그래프 (matplotlib 있으면)
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
)
from indicators import wilder_rsi, detect_divergence, volume_spike_ratio


def parse_args():
    p = argparse.ArgumentParser(description="신호별 과거 성과 백테스트")
    p.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="쉼표로 구분한 티커 목록 (생략하면 캐시된 스캔 유니버스 전체 사용)",
    )
    p.add_argument("--years", type=int, default=5, help="과거 몇 년치로 검증할지 (기본 5)")
    p.add_argument(
        "--horizons",
        type=str,
        default="5,10,20",
        help="진입 후 며칠(거래일) 뒤 수익률을 볼지, 쉼표구분 (기본 5,10,20)",
    )
    p.add_argument(
        "--telegram",
        action="store_true",
        help="백테스트 요약 결과를 Telegram으로도 전송 (config.py에 토큰/chat_id 설정되어 있어야 함)",
    )
    return p.parse_args()


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


HORIZON_LABELS = {5: "1주", 10: "2주", 15: "3주", 20: "1개월", 40: "2개월", 60: "3개월"}


def _horizon_label(h: int) -> str:
    friendly = HORIZON_LABELS.get(h)
    return f"{h}거래일({friendly})" if friendly else f"{h}거래일"


def build_telegram_summary(summary_df: pd.DataFrame, events_df: pd.DataFrame, tickers: list, years: int, horizons: list) -> str:
    """백테스트 요약을 Telegram 메시지 형태로 변환.
    실제 라이브 알림과 같은 신호명을 그대로 써서, "이 신호가 실제로 이렇게
    잘 작동하는지" 텔레그램에서 바로 확인할 수 있게 함.

    horizons에 넘긴 기간들을 전부(예: [10, 20] = 2주/1개월) 한 줄에 같이 보여줌."""
    lines = [
        f"🧪 [백테스트] 최근 {years}년, {len(tickers)}개 종목",
        f"(기준: {', '.join(_horizon_label(h) for h in horizons)} 뒤 수익률, 전체는 backtest_summary.csv 참고)",
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
                friendly = HORIZON_LABELS.get(h, f"{h}일")
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

    print(
        f"백테스트 대상: {len(tickers)}개 종목, 최근 {args.years}년, "
        f"진입 후 {horizons}거래일 뒤 수익률 검증"
    )

    data = yf.download(
        tickers,
        period=f"{args.years}y",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )

    all_events = []
    skipped = 0
    for ticker in tickers:
        try:
            df = data[ticker] if isinstance(data.columns, pd.MultiIndex) else data
            cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
            df = df[cols].dropna(how="all")
        except Exception:
            skipped += 1
            continue
        if len(df) < 250:
            skipped += 1
            continue

        sig = compute_signal_series(df)
        events = detect_entries(sig)
        if events.empty:
            continue
        events = add_forward_returns(events, sig, horizons)
        events.insert(0, "ticker", ticker)
        all_events.append(events)

    if skipped:
        print(f"(데이터 부족/조회 실패로 {skipped}개 종목 제외)")

    if not all_events:
        print("발생한 신호가 하나도 없습니다.")
        return

    events_df = pd.concat(all_events, ignore_index=True)
    events_df.to_csv("backtest_events.csv", index=False, encoding="utf-8-sig")
    print(f"\n개별 이벤트 {len(events_df)}건 -> backtest_events.csv 저장")

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
    summary_df.to_csv("backtest_summary.csv", index=False, encoding="utf-8-sig")

    print("\n=== 신호별 요약 ===")
    print(summary_df.to_string(index=False))
    print(
        "\n(win_rate = 그 기간 뒤 수익률이 +였던 비율. RSI 과매수/일목 하방 돌파처럼\n"
        " '하락 방향'을 노리는 신호는 오히려 마이너스 수익률이 신호가 잘 맞은\n"
        " 케이스일 수 있으니, 신호 성격에 맞춰 방향 감안해서 해석할 것.)"
    )

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
            ax.set_xlabel(f"{h}거래일 뒤 상승 비율 (%)")
            ax.set_title("신호별 승률")
            ax.axvline(50, color="gray", linestyle="--", linewidth=1)
            plt.tight_layout()
            plt.savefig("backtest_summary.png", dpi=150)
            if chosen_font:
                print("차트 -> backtest_summary.png 저장")
            else:
                print(
                    "차트 -> backtest_summary.png 저장 (한글 폰트를 못 찾아서 신호명이 "
                    "깨져 보일 수 있음 - '맑은 고딕' 등 한글 폰트 설치 후 다시 실행하면 해결됨)"
                )
    except ImportError:
        print("\n(matplotlib 없어서 차트는 생략함: pip install matplotlib 하면 다음번엔 생성됨)")

    if args.telegram:
        from notifier import send_telegram

        msg = build_telegram_summary(summary_df, events_df, tickers, args.years, horizons)
        send_telegram(msg)
        print("\nTelegram으로 요약 전송함 (안 오면 config.py의 토큰/chat_id 확인, 또는 로컬에서 직접 값 채워서 테스트)")


if __name__ == "__main__":
    main()
