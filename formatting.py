"""
formatting.py
알림 메시지 포맷팅 (일봉/4시간봉 공통).

같은 스캔에서 한 종목에 여러 신호가 동시에 뜨면:
  1) RSI/SMA 신호가 하필 "구름대 안(inside)"에서 발생했으면, 따로따로
     나열하지 않고 "☁️ 구름대 안에서 OO 발생" 식으로 묶어서 표시
     (가독성을 위해 - 일목구름대 자체 터치/돌파 알림과는 별개)
  2) 그 종목에 "지금 이 순간 동시에 활성 상태인" 신호가 2개 이상이면
     (오늘 새로 뜬 것 + 이미 지속중이던 것 다 포함해서) 어떤 신호끼리
     겹쳤는지 마지막 줄에 요약, 각각 (신규)/(기존) 표시
"""

# 이 신호들은 "구름대 안에서 발생"으로 묶일 수 있는 대상
# (일목구름대 상단/하단 터치 자체는 이미 구름 얘기라 여기 포함 안 함)
CLOUD_CONTEXT_TYPES = {
    "RSI 과매도 진입",
    "RSI 과매도 회복",
    "RSI 과매수 진입",
    "RSI 과매수 회복",
    "SMA120 터치",
    "SMA200 터치",
}


def format_alerts(alerts: list, title: str, footer: str = "") -> str:
    if not alerts:
        return title

    grouped = {}
    order = []
    for a in alerts:
        if a["ticker"] not in grouped:
            grouped[a["ticker"]] = []
            order.append(a["ticker"])
        grouped[a["ticker"]].append(a)

    lines = [title, ""]

    for ticker in order:
        ticker_alerts = grouped[ticker]
        first = ticker_alerts[0]
        change_str = f"{first['change_pct']:+.2f}%" if first["change_pct"] is not None else "N/A"
        cap_str = f"${first['market_cap_B']}B" if first.get("market_cap_B") else "N/A"

        lines.append(f"[{ticker}] ${first['close']} ({change_str}) | 시총 {cap_str}")

        inside_cloud = any(a.get("cloud_position") == "inside" for a in ticker_alerts)
        combinable = [a for a in ticker_alerts if a["signal_type"] in CLOUD_CONTEXT_TYPES]
        others = [a for a in ticker_alerts if a["signal_type"] not in CLOUD_CONTEXT_TYPES]

        if inside_cloud and combinable:
            names = " + ".join(a["signal_type"] for a in combinable)
            details = " / ".join(a["detail"] for a in combinable)
            lines.append(f"  ☁️ 구름대 안에서 {names} 발생 ({details})")
        else:
            for a in combinable:
                lines.append(f"  · [{a['signal_type']}] {a['detail']}")

        for a in others:
            lines.append(f"  · [{a['signal_type']}] {a['detail']}")

        if len(ticker_alerts) > 0:
            active = ticker_alerts[0].get("active_signals") or []
            if len(active) > 1:
                parts = [f"{s['label']}({'신규' if s['is_new'] else '기존'})" for s in active]
                lines.append(f"  ⚡ 동시 발생(겹침): {' + '.join(parts)}")

        lines.append("")

    if footer:
        lines.append(footer)

    return "\n".join(lines).rstrip()
