"""
kr_open_digest.py
한국 장 시작(09:00 KST) 20분 전에, 지금 활성 상태인(과매도/과매수/
SMA터치/일목터치/다이버전스) 모든 종목을 요약해서 알려주는 리마인더.

토스증권 등에서는 한국 장이 열리면 미국 주식도 같이 매매 가능해지는
경우가 많아서, 그 직전에 한 번 더 확인할 수 있게 하는 용도.

premarket_digest.py(미국 장 시작 전용)와 신호 계산 로직은 완전히 같고,
실행 시각 기준만 다름 - 이쪽은 한국시간(KST) 고정이라 서머타임 영향이
아예 없음 (한국은 서머타임 안 씀).

⚠️ 중요한 한계: 이 리마인더는 미국 정규장 마감(16:00 ET) 이후의
애프터마켓(연장거래) 가격 변동을 반영하지 못함. RSI/SMA/일목 신호는
전부 "정규장 종가" 기준으로 계산되기 때문에, 애프터마켓에서 가격이
움직여도 그 계산 자체는 안 바뀜. 즉 EOD Signal Report와 사실상 같은
내용을 한 번 더 보여주는 것 - "새 신호 감지"가 아니라 "한 번 더 상기
+ 혹시 EOD 리포트를 놓쳤을 때의 안전망" 용도로 이해할 것.

사용법:
  python kr_open_digest.py          # 정상 실행 (시간대+중복 체크 다 함)
  python kr_open_digest.py --test   # 시간대/중복 체크 건너뛰고 강제 전송
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

KST_TZ = ZoneInfo("Asia/Seoul")

# 한국 장 시작(09:00 KST) 20분 전 = 08:40 KST. cron 오차 감안해서
# 08:30~08:50 사이 아무 때나 실행되면 "그날의 리마인더"로 인정함.
WINDOW_START = (8, 30)
WINDOW_END = (8, 50)

SENT_MARKER_FILE = Path(__file__).parent / "kr_open_sent.json"


def in_kr_premarket_window(now_kst: datetime) -> bool:
    if now_kst.weekday() >= 5:  # 토/일 제외 (한국 거래일 기준)
        return False
    start = now_kst.replace(hour=WINDOW_START[0], minute=WINDOW_START[1], second=0, microsecond=0)
    end = now_kst.replace(hour=WINDOW_END[0], minute=WINDOW_END[1], second=0, microsecond=0)
    return start <= now_kst <= end


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
    parser = argparse.ArgumentParser(description="한국장 시작 20분 전 리마인더")
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드: 시간대/중복전송 체크 건너뛰고 강제로 전송. 마커 파일 저장 안 함.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    now_kst = datetime.now(KST_TZ)
    today_str = now_kst.strftime("%Y-%m-%d")

    if not args.test:
        if not in_kr_premarket_window(now_kst):
            print(f"[{now_kst}] 한국장 리마인더 시간대 아님, 스킵")
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
    title = f"{title_prefix}🇰🇷 한국장 시작 20분 전 리마인더 ({today_str})"
    footer = (
        "미국 정규장 마감(전날 종가) 기준 · 애프터마켓 가격변동은 미반영 "
        "(EOD Signal Report와 동일 내용, 재확인/안전망 용도)"
    )

    if not signals:
        msg = f"{title}\n\n지금 조건을 만족하는 종목이 하나도 없습니다.\n\n{footer}"
        print(msg)
        send_telegram(msg)
    else:
        msg = format_alerts(signals, title=title, footer=footer)
        print(msg)
        send_telegram(msg)

    if not args.test:
        mark_sent(today_str)


if __name__ == "__main__":
    main()
