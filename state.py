"""
state.py
장중 모니터링에서 같은 종목을 하루에 여러 번 알림 보내지 않도록
"오늘 이미 알림 보낸 티커" 목록을 파일로 저장/조회
"""

import json
from pathlib import Path

STATE_FILE = Path(__file__).parent / "alerted_today.json"


def load_alerted(today: str) -> set:
    """오늘 날짜 기준으로 이미 알림 보낸 티커 목록을 불러옴.
    날짜가 바뀌었으면 자동으로 초기화됨."""
    if not STATE_FILE.exists():
        return set()

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()

    if data.get("date") != today:
        return set()  # 날짜가 바뀜 -> 초기화

    return set(data.get("tickers", []))


def save_alerted(today: str, tickers: set):
    STATE_FILE.write_text(
        json.dumps({"date": today, "tickers": sorted(tickers)}, ensure_ascii=False),
        encoding="utf-8",
    )


def mark_alerted(today: str, new_tickers: list):
    """새로 알림 보낸 티커들을 기존 목록에 추가해서 저장"""
    alerted = load_alerted(today)
    alerted.update(new_tickers)
    save_alerted(today, alerted)
