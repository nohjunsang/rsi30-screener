"""
intraday_monitor.py
미국 정규장 시간에만 동작하는 4시간봉 종합 신호 조기경보
(RSI 과매도/회복, SMA120/200 터치, 일목균형표 구름대 터치 전부 체크).

Task Scheduler / GitHub Actions로 30분 간격 상시 실행되도록 등록하면,
이 스크립트가 알아서 "지금이 장중인지" 판단해서
장중이 아니면 아무것도 안 하고 바로 종료함.

주의: 4시간봉 신호는 "잠정치" 성격이 있음 (일봉보다 훨씬 자주 신호가
나오는 대신, 노이즈도 많음). 확정 신호는 여전히 main.py(장마감 후
자동 실행)가 담당함.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from h4_alerts import scan_h4_alerts
from notifier import send_telegram
from history import append_history
from formatting import format_alerts

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

    alerts, state = scan_h4_alerts()

    if not alerts:
        print(f"[{now_ny}] 새로운 4H 신호 없음")
        state.save()
        return

    title = f"🚨 4시간봉 장중 신호 ({now_ny.strftime('%Y-%m-%d %H:%M')} ET)"
    footer = "(장중 잠정치, 4시간봉 마감 전까지 변동 가능)"
    msg = format_alerts(alerts, title=title, footer=footer)

    print(msg)
    send_telegram(msg)
    append_history(alerts)
    state.save()


if __name__ == "__main__":
    main()
