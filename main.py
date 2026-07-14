"""
main.py
스크리너 실행 진입점

기본 사용법 (config.py 값 그대로 사용):
  pip install -r requirements.txt
  python main.py

조건을 그때그때 바꿔서 실행하고 싶으면:
  python main.py --market-cap 200 --rsi 35
  (시총 200B 이상, RSI 35 이하로 조건 변경해서 1회 실행. config.py는 안 건드림)
"""

import argparse

import pandas as pd

from config import MARKET_CAP_THRESHOLD, RSI_THRESHOLD
from screener import screen
from notifier import send_telegram


def parse_args():
    parser = argparse.ArgumentParser(description="RSI30 시총 스크리너")
    parser.add_argument(
        "--market-cap",
        type=float,
        default=MARKET_CAP_THRESHOLD / 1e9,
        help="시가총액 하한선 (단위: B달러, 기본값은 config.py의 MARKET_CAP_THRESHOLD)",
    )
    parser.add_argument(
        "--rsi",
        type=float,
        default=RSI_THRESHOLD,
        help="RSI 상한선 (기본값은 config.py의 RSI_THRESHOLD)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    market_cap_threshold = args.market_cap * 1e9

    df = screen(market_cap_threshold=market_cap_threshold, rsi_threshold=args.rsi)

    if df.empty:
        msg = (
            f"[{pd.Timestamp.today().date()}] "
            f"시총 {args.market_cap:.0f}B달러 이상 + RSI<={args.rsi} 종목 없음"
        )
        print(msg)
        send_telegram(msg)
        return

    print("\n=== 조건 충족 종목 ===")
    print(df.to_string(index=False))

    msg_lines = [
        f"📉 시총 {args.market_cap:.0f}B$+ / RSI<={args.rsi} 종목 ({df.iloc[0]['date']})"
    ]
    for _, row in df.iterrows():
        change_str = (
            f"{row['change_pct']:+.2f}%" if row["change_pct"] is not None else "N/A"
        )
        msg_lines.append(
            f"{row['ticker']}: ${row['close']} ({change_str}) | RSI {row['rsi']} | 시총 ${row['market_cap_B']}B"
        )
    send_telegram("\n".join(msg_lines))


if __name__ == "__main__":
    main()
