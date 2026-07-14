"""
history.py
알림이 나갈 때마다 기록을 남겨서, 나중에 "그 신호 이후 실제로
주가가 어떻게 움직였는지" 성과를 리뷰할 수 있게 함.

alert_history.json에 계속 추가(append)되는 방식이며,
GitHub Actions에서 git commit으로 저장소에 반영됨 (alerted_today.json과 동일 패턴).
"""

import json
from pathlib import Path
from datetime import datetime, timezone

HISTORY_FILE = Path(__file__).parent / "alert_history.json"


def append_history(records: list):
    """
    records: [{"ticker":.., "signal_type":.., "detail":.., "close":.., ...}, ...]
    각 레코드에 timestamp 자동 추가 후 파일에 append
    """
    if not records:
        return

    existing = []
    if HISTORY_FILE.exists():
        try:
            existing = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = []

    now = datetime.now(timezone.utc).isoformat()
    for r in records:
        r["logged_at_utc"] = now
        existing.append(r)

    HISTORY_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_history() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
