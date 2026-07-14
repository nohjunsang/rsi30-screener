"""
main.py
장마감 후 확정 리포트 실행 진입점 (일봉 기준: RSI 과매도/과매수 진입·회복 +
SMA120/200 터치 + 일목균형표 구름대 터치/돌파 종합).

미국 정규장 마감(16:00 ET) 직후에 최대한 바로 실행되도록 뉴욕시간
기준으로 시간대를 직접 판단함(서머타임 자동 반영, KST 환산 필요 없음).
마감 정각~+15분 사이에만 동작하고, 그 안에서도 하루 딱 1번만 실행되도록
날짜 기준 중복방지 처리함(eod_sent.json) - 워크플로우가 5분 간격으로
여러 번 깨어나도 실제로는 그 날의 첫 실행 때만 동작함.

마감 직후 15분 이내로 당긴 이유: 야후파이낸스 등 데이터 제공처가 정규장
종가를 확정하는 데 몇 분 정도 걸릴 수 있어서, 최소한의 안전 여유만 두고
최대한 빠르게 실행함 (애프터마켓 시간대에 걸쳐 신호를 놓치지 않도록).

사용법:
  pip install -r requirements.txt
  python refresh_cache.py   # 최초 1회 (또는 하루 1회) 캐시 생성 필요
  python main.py

테스트(휴장일 등 실제 신호 없이도 강제로 알림 확인하고 싶을 때):
  python main.py --test
  -> 시간대/중복전송 체크와 상태(중복방지) 전부 무시하고 지금 조건 충족하는
     신호를 전부 새 알림처럼 강제 전송함. 임시 상태로만 돌기 때문에 실제
     daily_state.json/eod_sent.json에는 저장되지 않음 (진짜 운영에 영향 없음).
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from alerts import scan_daily_alerts
from notifier import send_telegram
from history import append_history
from formatting import format_alerts

NY_TZ = ZoneInfo("America/New_York")

# 마감(16:00 ET) 정각부터 +15분까지만 "마감 직후"로 인정
CLOSE_TIME = (16, 0)
WINDOW_MINUTES_AFTER_CLOSE = 15

SENT_MARKER_FILE = Path(__file__).parent / "eod_sent.json"


def is_just_after_close(now_ny: datetime) -> bool:
    if now_ny.weekday() >= 5:
        return False
    close_t = now_ny.replace(hour=CLOSE_TIME[0], minute=CLOSE_TIME[1], second=0, microsecond=0)
    window_end = close_t + pd.Timedelta(minutes=WINDOW_MINUTES_AFTER_CLOSE)
    return close_t <= now_ny <= window_end


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
    parser = argparse.ArgumentParser(description="일봉 신호 리포트")
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드: 시간대/중복전송/상태 전부 무시하고 지금 조건 충족 신호를 전부 강제 전송. 저장 안 함.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    now_ny = datetime.now(NY_TZ)
    today_str = now_ny.strftime("%Y-%m-%d")

    if not args.test:
        if not is_just_after_close(now_ny):
            print(f"[{now_ny}] 장마감 직후 시간대 아님, 스킵")
            return
        if already_sent_today(today_str):
            print(f"[{today_str}] 오늘 리포트 이미 보냄, 스킵")
            return

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
            mark_sent(today_str)
        return

    title_prefix = "🧪 [테스트] " if args.test else ""
    msg = format_alerts(alerts, title=f"{title_prefix}📊 일봉 신호 리포트 ({today})")
    print(msg)
    send_telegram(msg)

    if not args.test:
        append_history(alerts)
        state.save()
        mark_sent(today_str)


if __name__ == "__main__":
    main()
