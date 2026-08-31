"""
kr_main.py
main.py의 국내주식 버전 - 한국장 마감 후 확정 리포트 실행 진입점.
한국은 서머타임이 없어서 미국 버전보다 시간대 계산이 단순함.

사용법:
  python kr_main.py
  python kr_main.py --test   # 시간대/중복전송 체크 무시하고 강제 전송, 상태 저장 안 함
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from alerts_kr import scan_kr_daily_alerts
from notifier import send_telegram
from history import append_history
from formatting import format_alerts

KST = ZoneInfo("Asia/Seoul")

# 한국장 마감(15:30) 정각부터 +180분(3시간)까지 "마감 직후"로 인정.
CLOSE_TIME = (15, 30)
WINDOW_MINUTES_AFTER_CLOSE = 180

SENT_MARKER_FILE = Path(__file__).parent / "kr_eod_sent.json"


def is_just_after_close(now_kst: datetime) -> bool:
    if now_kst.weekday() >= 5:
        return False
    close_t = now_kst.replace(hour=CLOSE_TIME[0], minute=CLOSE_TIME[1], second=0, microsecond=0)
    window_end = close_t + pd.Timedelta(minutes=WINDOW_MINUTES_AFTER_CLOSE)
    return close_t <= now_kst <= window_end


def already_sent_today(today_str: str) -> bool:
    if not SENT_MARKER_FILE.exists():
        return False
    try:
        data = json.loads(SENT_MARKER_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return data.get("last_sent") == today_str


def mark_sent(today_str: str):
    SENT_MARKER_FILE.write_text(json.dumps({"last_sent": today_str}), encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="한국장 일봉 신호 리포트")
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드: 시간대/중복전송/상태 전부 무시하고 강제 전송. 저장 안 함.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")

    if not args.test:
        if not is_just_after_close(now_kst):
            print(f"[{now_kst}] 한국장 마감 직후 시간대 아님, 스킵")
            return
        if already_sent_today(today_str):
            print(f"[{today_str}] 오늘 국장 리포트 이미 보냄, 스킵")
            return

    state_filename = "test_kr_daily_state_tmp.json" if args.test else None
    alerts, state = scan_kr_daily_alerts(state_filename=state_filename)
    today = pd.Timestamp.today().date()
    as_of = f"{today} 15:30 KST(한국장 마감) 종가 기준"

    if not alerts:
        msg = f"[{today}] 한국장 새로운 신호 없음 (일봉 기준)\n🕐 {as_of}"
        if args.test:
            msg = "🧪 [테스트] " + msg + " (지금 조건 충족하는 종목이 하나도 없음)"
        print(msg)
        send_telegram(msg)
        if not args.test:
            state.save()
            mark_sent(today_str)
        return

    title_prefix = "🧪 [테스트] " if args.test else ""
    msg = format_alerts(alerts, title=f"{title_prefix}📊 한국장 일봉 신호 리포트 ({today})", as_of=as_of)
    print(msg)
    send_telegram(msg)

    if not args.test:
        append_history(alerts)
        state.save()
        mark_sent(today_str)


if __name__ == "__main__":
    main()
