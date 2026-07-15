"""
notifier.py
Telegram 알림 전송
"""

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_MAX_LEN = 4000  # Telegram 메시지 길이 제한(4096자)보다 약간 여유있게


def _split_message_safely(message: str, max_len: int) -> list:
    """
    긴 메시지를 여러 개로 나눌 때, formatting.py가 넣은 HTML 태그
    (<b>...</b> 등)가 청크 중간에서 잘리지 않도록 임의의 글자 수가 아니라
    "빈 줄"(종목 블록 사이 구분) 단위로만 자름. 각 종목 블록 안에서는
    태그가 항상 자체적으로 열리고 닫히므로, 블록 경계에서만 자르면
    태그가 깨질 일이 없음.
    """
    blocks = message.split("\n\n")
    chunks = []
    current = ""

    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > max_len and current:
            chunks.append(current)
            current = block
        else:
            current = candidate

        # 블록 하나가 그 자체로 max_len을 넘는 초극단적인 경우(드묾)에도
        # 무한정 커지지 않도록, 일단 그대로 하나의 청크로 내보냄
        if len(current) > max_len:
            chunks.append(current)
            current = ""

    if current:
        chunks.append(current)

    return chunks


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(
            "[notifier] TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 비어있어서 "
            "전송을 스킵합니다. GitHub Secrets 또는 환경변수 설정을 확인하세요."
        )
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    for chunk in _split_message_safely(message, TELEGRAM_MAX_LEN):
        try:
            resp = requests.post(
                url,
                data={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "HTML"},
                timeout=10,
            )
            if resp.status_code != 200:
                print(
                    f"[notifier] Telegram 전송 실패 (HTTP {resp.status_code}): {resp.text[:300]}"
                )
        except requests.RequestException as e:
            print(f"[notifier] Telegram 전송 중 네트워크 오류: {e}")
