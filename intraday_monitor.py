"""
intraday_monitor.py
미국 프리마켓~애프터마켓 시간(04:00~20:00 ET)에 동작하는 4시간봉 종합
신호 조기경보 (RSI 과매도/과매수 진입·회복, SMA120/200 터치, 일목균형표
구름대 터치/돌파, RSI 다이버전스 전부 체크).

정규장(09:30~16:00 ET)뿐 아니라 프리마켓(04:00~09:30)/애프터마켓
(16:00~20:00)까지 포함해서 감시함 - 단, 프리/애프터마켓은 거래량이
정규장보다 훨씬 적어서 신호가 더 불안정(노이즈 많음)할 수 있고,
일부 종목은 데이터 자체가 부실할 수 있음. 정규장 신호에 비해 참고용으로
보는 게 안전함.

Task Scheduler / GitHub Actions로 30분 간격 상시 실행되도록 등록하면,
이 스크립트가 알아서 "지금이 감시 시간대인지" 판단해서
아니면 아무것도 안 하고 바로 종료함.

테스트(휴장일 등 감시 시간이 아니어도 강제로 알림 확인하고 싶을 때):
  python intraday_monitor.py --test
  -> 시간 체크를 건너뛰고, 상태(중복방지)도 무시해서 지금 조건
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

# 프리마켓 시작 ~ 애프터마켓 종료 (정규장 09:30~16:00 ET 포함)
MONITOR_START = (4, 0)    # 04:00 ET (프리마켓 시작)
MONITOR_END = (20, 0)     # 20:00 ET (애프터마켓 종료)


def is_monitor_time(now_ny: datetime) -> bool:
    if now_ny.weekday() >= 5:  # 5=토, 6=일
        return False

    start_t = now_ny.replace(hour=MONITOR_START[0], minute=MONITOR_START[1], second=0, microsecond=0)
    end_t = now_ny.replace(hour=MONITOR_END[0], minute=MONITOR_END[1], second=0, microsecond=0)
    return start_t <= now_ny <= end_t


def parse_args():
    parser = argparse.ArgumentParser(description="4시간봉 프리~애프터마켓 신호 모니터")
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드: 시간 체크 건너뛰고, 상태(중복방지)도 무시해서 지금 조건 충족 신호를 전부 강제 전송. 저장/히스토리 기록 안 함.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    now_ny = datetime.now(NY_TZ)

    if not args.test and not is_monitor_time(now_ny):
        print(f"[{now_ny}] 감시 시간대 아님, 스킵 (테스트하려면 --test 옵션 사용)")
        return

    state_filename = "test_h4_state_tmp.json" if args.test else None
    alerts, state = scan_h4_alerts(state_filename=state_filename)

    if not alerts:
        msg = f"[{now_ny.strftime('%Y-%m-%d %H:%M')} ET] 새로운 4H 신호 없음"
        if args.test:
            # 테스트 모드일 때만 "신호 없음"도 전송 (실제로 잘 도는지 확인용)
            msg = "🧪 [테스트] " + msg + " (지금 조건 충족하는 종목이 하나도 없음)"
            print(msg)
            send_telegram(msg)
        else:
            # 평상시엔 30분마다 도는 스캔이라, 신호 없을 때마다 텔레그램을
            # 보내면 스팸이 되므로 콘솔 로그만 남기고 조용히 넘어감
            print(msg)
            state.save()
        return

    title_prefix = "🧪 [테스트] " if args.test else ""
    title = f"{title_prefix}🚨 4시간봉 신호 ({now_ny.strftime('%Y-%m-%d %H:%M')} ET)"
    as_of = (
        f"스캔 실행 {now_ny.strftime('%H:%M')} ET 기준 · 실제 신호가 발생한 4H 봉 마감 시각은 "
        "이보다 최대 30분 정도 더 이를 수 있음"
    )
    footer = "(장중 잠정치, 4시간봉 마감 전까지 변동 가능 · 프리/애프터마켓은 유동성이 낮아 신호가 더 불안정할 수 있음)"
    if args.test:
        footer += " · 테스트 모드로 전송됨 - 실제 상태에는 저장 안 됨"

    msg = format_alerts(alerts, title=title, footer=footer, as_of=as_of)
    print(msg)
    send_telegram(msg)

    if not args.test:
        append_history(alerts)
        state.save()


if __name__ == "__main__":
    main()
