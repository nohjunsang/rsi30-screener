"""
notifier.py
Telegram 알림 전송
"""

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_MAX_LEN = 4000  # Telegram 메시지 길이 제한(4096자)보다 약간 여유있게


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # 메시지가 너무 길면(예: 첫 실행 때 신호가 한꺼번에 많이 뜨는 경우)
    # 여러 개로 나눠서 전송
    for i in range(0, len(message), TELEGRAM_MAX_LEN):
        chunk = message[i : i + TELEGRAM_MAX_LEN]
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": chunk})
