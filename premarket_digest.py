"""
premarket_digest.py
미국 정규장 시작(09:30 ET) 20분 전에, 지금 활성 상태인(과매도/과매수/
SMA터치/일목터치/다이버전스) 모든 종목을 요약해서 알려주는 리마인더.

전날 밤 EOD Signal Report가 이미 계산해둔 daily_state.json을 새로
다시 계산하는 게 아니라, 어제 종가 기준 daily 데이터를 다시 한 번
가볍게 훑어서(RSI/SMA/일목 신호 계산 자체는 전날 정규장 종가 기준
그대로임) 지금 조건을 만족하는 종목을 전부 정리함 - "새로 생긴 신호"만
걸러서 보여주는 평소 알림과 달리, 오늘 하루 참고할 수 있게 "지금
걸려있는 것 전체"를 한 번에 보여주는 용도.

각 종목 블록에는 🌙 프리마켓 줄로 "지금 시점" 실시간 시세와 전날
종가 대비 변동률도 같이 붙음(download_latest_quote, 1분봉+prepost=True) -
조회 실패 시엔 조용히 전날 종가만 표시됨.

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

from data import get_scan_universe, download_latest_quote
from toss_data import download_daily_data, extract_ticker_df
from engine import scan_current_snapshot
from formatting import format_alerts
from notifier import send_telegram

NY_TZ = ZoneInfo("America/New_York")

# 장 시작(09:30 ET) 20분 전 = 09:10 ET가 목표 시각이지만, GitHub Actions
# 예약 실행이 몇 시간씩 늦게 트리거되는 경우가 실제로 있어서(EOD에서
# 2026-08-04에 마감+1시간41분 지연 사례 확인됨) 09:00~12:00 사이 아무
# 때나 실행되면 "그날의 리마인더"로 넉넉하게 인정함. 중복 전송은
# premarket_sent.json(하루 1번 마커)이 막아주므로 넓게 잡아도 스팸 없음.
WINDOW_START = (9, 0)
WINDOW_END = (12, 0)

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

    if signals:
        involved = sorted({s["ticker"] for s in signals})
        quotes = download_latest_quote(involved)
        if not quotes:
            print("[premarket_digest] 프리마켓 실시간 시세 조회 실패 - 전날 종가만 표시합니다.")
        for s in signals:
            q = quotes.get(s["ticker"])
            if q and s.get("close"):
                s["live_price"] = q["price"]
                s["live_change_pct"] = round((q["price"] - s["close"]) / s["close"] * 100, 2)
                s["live_label"] = "프리마켓"

    title_prefix = "🧪 [테스트] " if args.test else ""
    title = f"{title_prefix}🔔 장 시작 20분 전 리마인더 ({today_str})"
    as_of = "RSI/SMA/일목 신호는 전날 정규장 종가 기준 · 🌙 프리마켓 줄의 가격은 지금 시점 실시간 시세"
    footer = "전날 종가 기준 신호 + 🌙 프리마켓 줄이 있는 종목은 가격만 지금 시점 실시간 반영 (신규 여부와 무관)"

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
