"""
main.py
장마감 후 확정 리포트 실행 진입점 (일봉 기준: RSI 과매도/회복 +
SMA120/200 터치 + 일목균형표 구름대 터치 종합).

사용법:
  pip install -r requirements.txt
  python refresh_cache.py   # 최초 1회 (또는 하루 1회) 캐시 생성 필요
  python main.py
"""

import pandas as pd

from alerts import scan_daily_alerts
from notifier import send_telegram
from history import append_history
from formatting import format_alerts


def main():
    alerts, state = scan_daily_alerts()
    today = pd.Timestamp.today().date()

    if not alerts:
        msg = f"[{today}] 새로운 신호 없음 (일봉 기준)"
        print(msg)
        send_telegram(msg)
        state.save()
        return

    msg = format_alerts(alerts, title=f"📊 일봉 신호 리포트 ({today})")
    print(msg)
    send_telegram(msg)
    append_history(alerts)
    state.save()


if __name__ == "__main__":
    main()
