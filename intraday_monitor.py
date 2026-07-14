"""
intraday_monitor.py
미국 정규장 시간에만 동작하는 장중 모니터링.
Task Scheduler로 15분 간격 상시 실행되도록 등록하면,
이 스크립트가 알아서 "지금이 장중인지" 판단해서
장중이 아니면 아무것도 안 하고 바로 종료함 (비용/시간 거의 안 듦).

장중일 때는:
  1) screener.screen()으로 조건(시총+RSI) 통과 종목 스크리닝
     (yfinance 일봉 데이터는 장중에는 "오늘"의 진행 중인 가격을
      잠정 종가처럼 반영하기 때문에, 장중 RSI 추정치로 쓸 수 있음)
  2) 오늘 이미 알림 보낸 종목은 건너뜀 (state.py가 중복 방지)
  3) 새로 조건 통과한 종목만 Telegram으로 알림
     (현재가, 등락율, RSI, 시총 포함)

주의: 장중 RSI는 "잠정치"임. 장 마감 전까지 가격이 바뀌면 RSI도
바뀌기 때문에, 실제 "일봉 마감 확정" 스크리닝은 main.py(장마감 후
자동 실행)가 따로 담당함. 이 스크립트는 조기 경보 용도로 보면 됨.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from screener import screen
from notifier import send_telegram
from state import load_alerted, mark_alerted

NY_TZ = ZoneInfo("America/New_York")

MARKET_OPEN = (9, 30)   # 09:30 ET
MARKET_CLOSE = (16, 0)  # 16:00 ET


def is_market_open(now_ny: datetime) -> bool:
    if now_ny.weekday() >= 5:  # 5=토, 6=일
        return False

    open_t = now_ny.replace(hour=MARKET_OPEN[0], minute=MARKET_OPEN[1], second=0, microsecond=0)
    close_t = now_ny.replace(hour=MARKET_CLOSE[0], minute=MARKET_CLOSE[1], second=0, microsecond=0)
    return open_t <= now_ny <= close_t


def main():
    now_ny = datetime.now(NY_TZ)

    if not is_market_open(now_ny):
        print(f"[{now_ny}] 장 시간 아님, 스킵")
        return

    today = now_ny.strftime("%Y-%m-%d")
    already_alerted = load_alerted(today)

    df = screen()
    if df.empty:
        print(f"[{now_ny}] 조건 통과 종목 없음")
        return

    new_hits = df[~df["ticker"].isin(already_alerted)]
    if new_hits.empty:
        print(f"[{now_ny}] 새로운 알림 대상 없음 (이미 오늘 다 알림 보냄)")
        return

    for _, row in new_hits.iterrows():
        change_str = (
            f"{row['change_pct']:+.2f}%" if row["change_pct"] is not None else "N/A"
        )
        msg = (
            f"🚨 [장중 잠정] RSI 30 이하 진입\n"
            f"{row['ticker']}\n"
            f"현재가: ${row['close']} ({change_str})\n"
            f"RSI(14): {row['rsi']} (장중 잠정치, 마감 전까지 변동 가능)\n"
            f"시총: ${row['market_cap_B']}B\n"
            f"기준: {now_ny.strftime('%Y-%m-%d %H:%M')} ET"
        )
        print(msg)
        send_telegram(msg)

    mark_alerted(today, new_hits["ticker"].tolist())


if __name__ == "__main__":
    main()
