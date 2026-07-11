"""
state.py
종목별로 "지금 어떤 신호 상태인지"를 파일에 저장해두고,
상태가 바뀌는 순간(전이, transition)에만 알림을 보내도록 하는 범용 상태 저장소.

예: RSI가 계속 30 이하에 머물러 있어도 매번 알림이 오지 않고,
"정상 -> 과매도로 넘어가는 순간"과 "과매도 -> 정상(회복)으로 넘어가는 순간"에만
알림이 나가도록 함.
"""

import json
from pathlib import Path


class StateStore:
    def __init__(self, filename: str):
        self.path = Path(__file__).parent / filename
        self._data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self):
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, ticker: str, key: str, default=None):
        return self._data.get(ticker, {}).get(key, default)

    def set(self, ticker: str, key: str, value):
        self._data.setdefault(ticker, {})[key] = value

    def check_transition(self, ticker: str, key: str, new_value: str) -> bool:
        """
        이전 상태와 다르면(=전이 발생) True를 반환하고 상태를 갱신함.
        같으면 False (알림 안 보내도 됨).
        """
        old_value = self.get(ticker, key)
        if old_value == new_value:
            return False
        self.set(ticker, key, new_value)
        return True

    def exists_on_disk(self) -> bool:
        return self.path.exists()
