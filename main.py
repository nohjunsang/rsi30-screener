"""
main.py
장마감 후 확정 리포트 실행 진입점 (일봉 기준: RSI 과매도/과매수 진입·회복 +
SMA120/200 터치 + 일목균형표 구름대 터치/돌파 종합).

사용법:
  pip install -r requirements.txt
  python refresh_cache.py   # 최초 1회 (또는 하루 1회) 캐시 생성 필요
  python main.py

테스트(휴장일 등 실제 신호 없이도 강제로 알림 확인하고 싶을 때):
  python main.py --test
  -> 상태(중복방지) 무시하고 지금 조건 충족하는 신호를 전부 새 알림처럼
     전송함. 임시 상태로만 돌기 때문에 실제 daily_state.json에는
     저장되지 않고, 알림 히스토리에도 안 남음 (진짜 운영에 영향 없음).
"""

import argparse

import pandas as pd

from alerts import scan_daily_alerts
from notifier import send_telegram
from history import append_history
from formatting import format_alerts


def parse_args():
    parser = argparse.ArgumentParser(description="일봉 신호 리포트")
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드: 상태(중복방지) 무시하고 지금 조건 충족 신호를 전부 강제 전송. 저장/히스토리 기록 안 함.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    state_filename = "test_daily_state_tmp.json" if args.test else None

    alerts, state = scan_daily_alerts(state_filename=state_filename)
    today = pd.Timestamp.today().date()

    if not alerts:
        msg = f"[{today}] 새로운 신호 없음 (일봉 기준)"
        if args.test:
            msg = "🧪 [테스트] " + msg + " (지금 조건 충족하는 종목이 하나도 없음 - 실제로 아무 신호도 없는 상태)"
        print(msg)
        send_telegram(msg)
        if not args.test:
            state.save()
        return

    title_prefix = "🧪 [테스트] " if args.test else ""
    msg = format_alerts(alerts, title=f"{title_prefix}📊 일봉 신호 리포트 ({today})")
    print(msg)
    send_telegram(msg)

    if not args.test:
        append_history(alerts)
        state.save()


if __name__ == "__main__":
    main()
