"""
intraday_monitor.py
미국 정규장 시간에만 동작하는 4시간봉 종합 신호 조기경보
(RSI 과매도/과매수 진입·회복, SMA120/200 터치, 일목균형표 구름대
터치/돌파 전부 체크).

Task Scheduler / GitHub Actions로 30분 간격 상시 실행되도록 등록하면,
이 스크립트가 알아서 "지금이 장중인지" 판단해서
장중이 아니면 아무것도 안 하고 바로 종료함.

테스트(휴장일 등 장 시간이 아니어도 강제로 알림 확인하고 싶을 때):
  python intraday_monitor.py --test
  -> 장 시간 체크를 건너뛰고, 상태(중복방지)도 무시해서 지금 조건
     충족하는 신호를 전부 새 알림처럼 전송함. 임시 상태로만 돌기 때문에
     실제 h4_state.json에는 저장 안 되고, 히스토리에도 안 남음.
"""

import argparse
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


def parse_args():
    parser = argparse.ArgumentParser(description="4시간봉 장중 신호 모니터")
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드: 장시간 체크 건너뛰고, 상태(중복방지)도 무시해서 지금 조건 충족 신호를 전부 강제 전송. 저장/히스토리 기록 안 함.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    now_ny = datetime.now(NY_TZ)

    if not args.test and not is_market_open(now_ny):
        print(f"[{now_ny}] 장 시간 아님, 스킵 (테스트하려면 --test 옵션 사용)")
        return

    state_filename = "test_h4_state_tmp.json" if args.test else None
    alerts, state = scan_h4_alerts(state_filename=state_filename)

    if not alerts:
        msg = f"[{now_ny.strftime('%Y-%m-%d %H:%M')} ET] 새로운 4H 신호 없음"
        if args.test:
            msg = "🧪 [테스트] " + msg + " (지금 조건 충족하는 종목이 하나도 없음)"
        print(msg)
        send_telegram(msg)
        if not args.test:
            state.save()
        return

    title_prefix = "🧪 [테스트] " if args.test else ""
    title = f"{title_prefix}🚨 4시간봉 장중 신호 ({now_ny.strftime('%Y-%m-%d %H:%M')} ET)"
    footer = "(장중 잠정치, 4시간봉 마감 전까지 변동 가능)"
    if args.test:
        footer += " · 테스트 모드로 전송됨 - 실제 상태에는 저장 안 됨"

    msg = format_alerts(alerts, title=title, footer=footer)
    print(msg)
    send_telegram(msg)

    if not args.test:
        append_history(alerts)
        state.save()


if __name__ == "__main__":
    main()
