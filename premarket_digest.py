"""
premarket_digest.py
미국 정규장 시작(09:30 ET) 20분 전에, 지금 활성 상태인(과매도/과매수/
SMA터치/일목터치/다이버전스) 모든 종목을 요약해서 알려주는 리마인더.

전날 밤 EOD Signal Report가 이미 계산해둔 daily_state.json을 새로
다시 계산하는 게 아니라, 어제 종가 기준 daily 데이터를 다시 한 번
가볍게 훑어서(가격 자체는 어차피 장 시작 전이라 안 바뀌어 있음) 지금
조건을 만족하는 종목을 전부 정리함 - "새로 생긴 신호"만 걸러서 보여주는
평소 알림과 달리, 오늘 하루 참고할 수 있게 "지금 걸려있는 것 전체"를
한 번에 보여주는 용도.

하루 한 번만 보내지도록 날짜 기준으로 중복 방지함 (premarket_sent.json).

사용법:
  python premarket_digest.py          # 정상 실행 (장시간+중복 체크 다 함)
  python premarket_digest.py --test   # 시간/중복 체크 건너뛰고 강제 전송
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from data import get_scan_universe, download_daily_data, extract_ticker_df
from engine import scan_current_snapshot
from formatting import format_alerts
from notifier import send_telegram

NY_TZ = ZoneInfo("America/New_York")

# 장 시작(09:30 ET) 20분 전 = 09:10 ET. cron 오차/재실행 감안해서
# 09:00~09:20 사이 아무 때나 실행되면 "그날의 리마인더"로 인정함.
WINDOW_START = (9, 0)
WINDOW_END = (9, 20)

SENT_MARKER_FILE = Path(__file__).parent / "premarket_sent.json"


def in_premarket_window(now_ny: datetime) -> bool:
    if now_ny.weekday() >= 5:  # 토/일 제외
        return False
    start = now_ny.replace(hour=WINDOW_START[0], minute=WINDOW_START[1], second=0, microsecond=0)
    end = now_ny.replace(hour=WINDOW_END[0], minute=WINDOW_END[1], second=0, microsecond=0)
    return start <= now_ny <= end


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
    parser = argparse.ArgumentParser(description="장 시작 20분 전 리마인더")
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드: 시간대/중복전송 체크 건너뛰고 강제로 전송 (마커 파일 저장 안 함)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    now_ny = datetime.now(NY_TZ)
    today_str = now_ny.strftime("%Y-%m-%d")

    if not args.test:
        if not in_premarket_window(now_ny):
            print(f"[{now_ny}] 리마인더 시간대 아님, 스킵")
            return
        if already_sent_today(today_str):
            print(f"[{today_str}] 오늘 이미 리마인더 보냄, 스킵")
            return

    tickers = get_scan_universe()
    print(f"스캔 대상 종목 수: {len(tickers)}")
    if not tickers:
        print("스캔 대상이 없습니다. refresh_cache.py를 먼저 실행했는지 확인하세요.")
        return

    data = download_daily_data(tickers)

    def get_df(ticker):
        return extract_ticker_df(data, ticker)

    signals = scan_current_snapshot(
        tickers, get_df, cross_state_filename="h4_state.json", cross_label="4H"
    )

    title_prefix = "🧪 [테스트] " if args.test else ""
    title = f"{title_prefix}🔔 장 시작 20분 전 리마인더 ({today_str})"
    as_of = "전날 미국 정규장 종가 기준 스냅샷 (오늘 프리마켓 가격변동 미반영)"
    footer = "전날 종가 기준 · 지금 조건을 만족 중인 종목 전체 요약 (신규 여부와 무관)"

    if not signals:
        msg = f"{title}\n🕐 {as_of}\n\n지금 조건을 만족하는 종목이 하나도 없습니다."
        print(msg)
        send_telegram(msg)
    else:
        msg = format_alerts(signals, title=title, footer=footer, as_of=as_of)
        print(msg)
        send_telegram(msg)

    if not args.test:
        mark_sent(today_str)


if __name__ == "__main__":
    main()
